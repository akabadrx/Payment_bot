import os
import json
import logging
import html as _html
from datetime import datetime
from typing import List, Optional

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config

logger = logging.getLogger(__name__)

# --- KNOWN USERS HELPERS ---
def load_known_users():
    if os.path.exists(config.KNOWN_USERS_FILE):
        with open(config.KNOWN_USERS_FILE, "r") as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

def save_known_user(chat_id):
    users = load_known_users()
    if chat_id not in users:
        users.add(chat_id)
        with open(config.KNOWN_USERS_FILE, "w") as f:
            json.dump(list(users), f)

# --- GOOGLE SERVICES ---
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(config.SERVICE_ACCOUNT_FILE, scope)
    return gspread.authorize(creds)

def get_drive_service():
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        config.SERVICE_ACCOUNT_FILE,
        ['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=creds)

def grant_expert_drive_access(email: str) -> bool:
    try:
        service = get_drive_service()
        permission = {
            'type': 'user',
            'role': 'reader',
            'emailAddress': email
        }
        service.permissions().create(
            fileId=config.EXPERT_COURSE_DRIVE_FOLDER_ID,
            body=permission,
            fields='id',
        ).execute()
        logger.info(f"Granted Expert Drive access to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to grant Expert Drive access to {email}: {e}")
        return False

def grant_highschool_drive_access(email: str) -> bool:
    try:
        service = get_drive_service()
        permission = {
            'type': 'user',
            'role': 'reader',
            'emailAddress': email
        }
        service.permissions().create(
            fileId=config.HIGHSCHOOL_COURSE_DRIVE_FOLDER_ID,
            body=permission,
            fields='id',
        ).execute()
        logger.info(f"Granted Highschool Drive access to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to grant Highschool Drive access to {email}: {e}")
        return False

# --- TEXT & FORMATTING HELPERS ---
def _format_amount(n: int):
    return "{:,.0f}".format(n)

def build_payment_text(method_key, course_key, kids_count=0, hs_count=0, discount_percent=0):
    method = method_key
    if method not in config.PRICES:
        return "عذراً، طريقة الدفع غير متاحة حالياً."

    price_map = config.PRICES[method]
    unit = price_map["currency"]
    
    unit_amount = 0
    if course_key == "kids":
        unit_amount = price_map["kids"]
    elif course_key == "highschool":
        unit_amount = price_map.get("highschool", 0)
    else:
        unit_amount = price_map.get(course_key, 0)
        
    total = unit_amount
    per_note = ""
    
    if course_key == "kids":
        k = max(1, int(kids_count or 1))
        total = unit_amount * k
        per_note = f" (لكل طفل {unit_amount} {unit})"
    elif course_key == "highschool":
        k = max(1, int(hs_count or 1))
        total = unit_amount * k
        per_note = f" (لكل متدرب {unit_amount} {unit})"
    
    # Apply discount
    discount_msg = ""
    if discount_percent and discount_percent > 0:
        original = total
        discount_amount = (total * discount_percent) / 100
        total = total - discount_amount
        # Make it integer if possible
        if int(total) == total:
            total = int(total)
        discount_msg = f"🎉 **تم تطبيق خصم {discount_percent}%!**\n💰 السعر الأصلي: {_format_amount(original)} {unit}\n"

    # Method-specific static fields
    header = ""
    body = ""
    
    if method == "saudi":
        header = "الدفع عبر تحويل بنكي مباشر (السعودية):"
        body = (
            "الاسم:  علي محمد فضل الله بادي\n"
            "البنك:  البنك الأهلي السعودي\n"
            "الآيبان:  SA2410000011100312428804\n"
            "رقم الحساب:  11100312428804\n"
            "رمز سويفت:  NCBKSAJE"
        )
    elif method == "uae":
        header = "الدفع عبر تحويل بنكي مباشر (الإمارات):"
        body = (
            "اسم صاحب الحساب:  MORWAN MOHAMED\n"
            "اسم البنك:  بنك الماريه المحلي\n"
            "رقم الحساب:  5270516520000001\n"
            "الآيبان:  AE570975270516520000001\n"
            "العملة:  AED"
        )
    elif method == "wu_mg":
        header = "الدفع عبر Western Union / MoneyGram:"
        body = (
            "الاسم:  BADOR IBRAHIM ALFAKI KHALID\n"
            "الدولة:  RWANDA\n"
            "رقم الهاتف:  +250735721744"
        )
    elif method == "rwanda":
        header = "الدفع عبر محفظة الهاتف (رواندا):"
        body = (
            "مفتاح رواندا:  250\n"
            "محفظة مومو:  0795342923\n"
            "محفظة ايرتيل:  0735721744"
        )
    elif method == "bankak":
        header = "الدفع عبر بنكك (السودان):"
        body = (
            "رقم حساب بنكك:  3277030\n"
            "باسم:  بدر إبراهيم"
        )
    elif method == "vodafone_eg":
        header = "الدفع عبر فودافون كاش / انستا باي (مصر):"
        body = (
            f"رقم فودافون كاش / انستا باي : محمد خالد {config.VODAFONE_EG_NUMBER}\n"
            "بعد التحويل، يُرجى إرسال لقطة شاشة (Screenshot) لعملية الدفع لتأكيد الاستلام و منحك الوصول لمحتوى الدورة مباشرة. شكرًا لك 🌟"
        )
    elif method == "iban":
        header = "التحويل البنكي عبر IBAN (دولي):"
        body = (
            f"اسم صاحب الحساب:  {config.IBAN_ACCOUNT_NAME}\n"
            f"اسم البنك:  {config.IBAN_BANK_NAME}\n"
            f"الآيبان (IBAN):  {config.IBAN_NUMBER}\n"
            f"سويفت (SWIFT):  {config.IBAN_SWIFT}\n"
            f"ملاحظات التحويل:  {config.IBAN_NOTES}"
        )
    elif method == "paypal":
        header = "الدفع عبر PayPal:"
        body = (
            f"رابط الدفع:  {config.PAYPAL_LINK}\n"
            f"ملاحظات:  {config.PAYPAL_NOTES}\n"
            "بعد الدفع أرسل صورة الإيصال هنا مباشرة."
        )
    else:
        header, body = "طريقة الدفع", ""

    lines = []
    lines.append(f"💳 {header}\n")
    lines.append(body + "\n")
    
    if discount_msg:
        lines.append(discount_msg)
        lines.append(f"🏷️ **السعر بعد الخصم:** { _format_amount(total) } {unit}{per_note}\n")
    elif course_key == "kids" or course_key == "highschool":
        lines.append(f"\nالرسوم: { _format_amount(total) } {unit}{per_note}\n")
    else:
        lines.append(f"\nالرسوم: { _format_amount(total) } {unit}\n")

    lines.append("\nبعد الدفع، أرسل صورة إيصال الدفع هنا مباشرة.\n")
    if method == "wu_mg":
        lines.append("ثم أرسل في رسالة واحدة: الاسم الكامل / الدولة / الرقم المرجعي (MTCN).\n")

    return "\n".join(lines)

def save_to_google_sheet(user_info):
    try:
        client = get_gspread_client()
        sheet = client.open(config.GOOGLE_SHEET_NAME).sheet1

        course_key = user_info.get("course")

        # merge kids info into details column if present
        kids_info = ""
        if course_key == "kids":
            kc = user_info.get("kids_count")
            kn = user_info.get("kids_names")
            if kc:
                kids_info = f"Kids: {kc} | Names: {kn or ''}"
        elif course_key == "highschool":
            hc = user_info.get("hs_count")
            hn = user_info.get("hs_names")
            if hc:
                kids_info = f"Highschool: {hc} | Names: {hn or ''}"

        # --- build merged details (proper indentation) ---
        merged_details_parts = []
        # Always include WhatsApp number for all courses
        wa = user_info.get("whatsapp")
        if wa:
            merged_details_parts.append(f"WA: {wa}")
        if user_info.get("wu_details"):
            merged_details_parts.append(f"WU: {user_info['wu_details']}")
        if user_info.get("vodafone_details"):
            merged_details_parts.append(f"Vodafone: {user_info['vodafone_details']}")
        if kids_info:
            merged_details_parts.append(kids_info)

        merged_details = " | ".join(merged_details_parts) if merged_details_parts else ""

        course_title = config.COURSES.get(course_key, {}).get("title", "غير محدد")

        row = [
            user_info.get("name", "N/A"),
            user_info.get("email", "N/A"),
            course_title,
            user_info.get("payment_method", "N/A"),
            user_info.get("amount_paid", "N/A"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"@{user_info.get('telegram_username', 'N/A')}",
            "🕐 Waiting",
            merged_details,
        ]

        sheet.append_row(row, value_input_option="USER_ENTERED")
        return len(sheet.get_all_values())

    except Exception as e:
        logger.error(f"Failed to save to Google Sheet: {e}")
        raise

def update_status_in_sheet(row_number, new_status):
    try:
        client = get_gspread_client()
        sheet = client.open(config.GOOGLE_SHEET_NAME).sheet1
        sheet.update_cell(row_number, 8, new_status)  # Column H
    except Exception as e:
        logger.error(f"Failed to update Google Sheet: {e}")
        raise

# --- APPROVAL MESSAGES ---
def _msg_expert(user_info: dict) -> List[str]:
    # email = _html.escape(user_info.get("email", "") or "بريدك") # unused in original logic
    return [
  "🎉 تم تأكيد الدفع بنجاح!\n\n"
    "أهلاً وسهلاً بك في 🧠 <b>كورس خبير الذاكرة (Memory Expert)</b>!\n"
    "يسعدنا جدًا وجودك معنا في هذه الرحلة لتقوية ذاكرتك وتطوير قدراتك العقلية.\n\n"

    "إليك الخطوات التي تساعدك على البدء فوراً 👇\n\n"

    "1️⃣ <b>الوصول إلى الكورس على Google Drive:</b>\n"
    "تم ربط بريدك الإلكتروني المسجّل بصلاحية الدخول إلى مجلد الكورس.\n"
    "افتح الرابط التالي باستخدام نفس الإيميل الذي سجلت به:\n"
    "https://drive.google.com/drive/folders/1YsLGSWPvZJSkMFVtRbBltJZsPowmTClj?usp=drive_link\n"
    "لو ظهرت لك مشكلة في الدخول، تواصل مع خدمة العملاء لإصلاح الصلاحيات.\n\n"

    "2️⃣ بعد حصولك على الوصول، افتح مجلد <b>“خبير الذاكرة”</b> وستجد بداخله:\n"
    "📄 ملف <b>PDF بعنوان “دليل كورس خبير الذاكرة”</b>\n"
    "اقرأ هذا الملف كاملاً قبل مشاهدة أي محاضرة، لأنه يحتوي على الجدول الأسبوعي، "
    "روابط التطبيقات، وطريقة إرسال التمارين.\n\n"

    "3️⃣ <b>انضم إلى قروب التليجرام الرسمي:</b>\n"
    "https://t.me/+AANGJtBLqGc0MWNk\n"
    "في القروب ستشارك تمارينك اليومية، وتطرح أسئلتك، وتتلقى المتابعة المباشرة من د. بدر.\n\n"

    "4️⃣ أرسل في القروب صور تمارينك أو استفساراتك لتحصل على تصحيح ومتابعة مباشرة.\n\n"

    "5️⃣ <b>السيشن الشهري المباشر</b> يُقام كل <b>أول جمعة من كل شهر</b> عبر Google Meet، "
    "وسيُنشر الرابط في القروب قبل الموعد.\n\n"

    "6️⃣ الكورس يبدأ مباشرة بعد تسجيلك، لذلك توجّه الآن إلى مجلد Google Drive، "
    "ابدأ بقراءة الدليل ثم شاهد أول محاضرة وطبّق التمارين خطوة بخطوة.\n\n"

    "7️⃣ المحاضرات متاحة مدى الحياة، لكن يُفضل الالتزام بالجدول الأسبوعي "
    "المذكور في الدليل لتبني عادة تدريب قوية وتستفيد أقصى استفادة.\n\n"

    "🚀 جاهز؟ ابدأ الآن من ملف الدليل، وشارك أول تمرين لك في القروب اليوم!\n\n"
    f"لأي استفسار أو دعم فني، يمكنك التواصل مع خدمة العملاء: {config.CUSTOMER_SUPPORT_USERNAME}!"
    ]

def _msg_kids(user_info: dict) -> List[str]:
    kc = user_info.get("kids_count")
    kn = user_info.get("kids_names")
    kids_line = ""
    if kc:
        kids_line = f"\n👨‍👩‍👧 عدد الأطفال: {kc}\n"
    if kn:
        kids_line += f"الأسماء: {kn}\n"

    return [
        (
            "✅ تم تأكيد الدفع بنجاح\n\n"
            "مرحباً بكم في برنامج Super Kids Memory لتقنيات الذاكرة للأطفال 🎉\n"
            "متحمسين نبدأ مع أطفالكم رحلة ممتعة نحو ذاكرة أقوى وتحصيل دراسي أفضل.\n\n"
            "📅 مدة البرنامج وجدول الجلسات\n"
            "• ٨ جلسات تدريبية\n"
            "• جلسة واحدة أسبوعياً كل يوم سبت الساعة 12 ظهراً بتوقيت السعودية\n"
            "• مدة الجلسة: ٦٠ دقيقة عبر Zoom\n\n"
            "🎯 أهداف البرنامج\n"
            "• تعليم تقنيات الذاكرة بأسلوب ممتع وتطبيقي\n"
            "• رفع الحفظ والفهم الأكاديمي\n"
            "• بناء الثقة بالنفس وتحفيز حب التعلّم\n"
            "• متابعة بسيطة وسهلة مع ولي الأمر لضمان أفضل نتيجة\n"
            f"{kids_line}"
            "\n📩 خطوة مهمة:\n"
            "لإكمال تسجيلكم وإضافتكم إلى قروب الكورس + قروب التليجرام للمتابعة\n"
            "يرجى إرسال رسالة على الواتساب عبر الرابط التالي:\n"
            "https://wa.me/250735721744\n\n"
            "🚀 نتمنى لأطفالكم بداية قوية ومليئة بالمتعة والتطور في رحلتهم مع الذاكرة!"
        )
    ]

def _msg_highschool(user_info: dict) -> List[str]:
    hc = user_info.get("hs_count")
    hn = user_info.get("hs_names")
    hs_line = ""
    if hc or hn:
        hs_line = f"\n🎓 عدد المتدربين: {hc or '-'} | الأسماء: {hn or '-'}\n"

    return [
        "🎉 تم تأكيد الدفع بنجاح!\n\n"
        "أهلاً وسهلاً بكم في 🎓 <b>برنامج تدريب طلاب الشهادة الثانوية</b>!\n"
        "يسعدنا جداً وجودكم معنا في هذه الرحلة لتقوية الذاكرة والتفوق الأكاديمي.\n\n"
        "إليك الخطوات التي تساعدك على البدء فوراً 👇\n\n"
        "1️⃣ <b>الوصول إلى الكورس على Google Drive:</b>\n"
        "تم ربط بريدك الإلكتروني المسجّل بصلاحية الدخول إلى مجلد الكورس.\n"
        "افتح الرابط التالي باستخدام نفس الإيميل الذي سجلت به:\n"
        "https://drive.google.com/drive/folders/1iAF-DRCuDHXDzAZsex_0HEtQ0NNg2LYI?usp=drive_link\n"
        "لو ظهرت لك مشكلة في الدخول، تواصل مع خدمة العملاء لإصلاح الصلاحيات.\n\n"
        "2️⃣ <b>انضم إلى قروبات المتابعة:</b>\n"
        "• قروب الواتساب للتواصل اليومي:\n"
        "https://chat.whatsapp.com/Iw1M89AyDOS1Ih0eeATOs6\n\n"
        "• قروب التليجرام للدعم والمتابعة:\n"
        "https://t.me/+sjJprqP_snw4ZDY8\n\n"
        "في القروبات ستجد التمارين اليومية، التحديثات، والدعم المباشر من د. بدر.\n\n"
        "3️⃣ <b>ورش العمل الشهرية:</b>\n"
        "يُقام ورشة عملية لايف مرة كل شهر، وسيُنشر موعدها ورابطها في القروبات قبل الموعد.\n\n"
        f"{hs_line}"
        "4️⃣ <b>ابدأ الآن:</b>\n"
        "توجّه الآن إلى مجلد Google Drive، شاهد المحاضرات، وطبّق التمارين خطوة بخطوة.\n"
        "المحاضرات متاحة للمشاهدة في أي وقت، مع متابعة يومية لحد يوم الامتحان.\n\n"
        "🚀 جاهز؟ ابدأ اليوم وشارك تقدمك في القروبات!\n\n"
        f"لأي استفسار أو دعم فني، تواصل مع خدمة العملاء: {config.CUSTOMER_SUPPORT_USERNAME}"
    ]

def _msg_private(user_info: dict) -> list[str]:
    return [
        "✅ تم تأكيد الدفع!\n\n"
        "مرحباً بك في برنامج التدريب الشخصي 🎉",
        (
            "📞 هذا برنامج فردي مباشر مع د. بدر.\n\n"
            "⚡ للتنسيق حول مواعيد الجلسات:\n"
            f"1️⃣ التقط سكرين شوت لرسالة تأكيد الدفع هذه.\n"
            f"2️⃣ أرسلها مباشرة لخدمة العملاء عبر الواتساب:\n👉 {config.CUSTOMER_SUPPORT_USERNAME}\n\n"
            "بعدها ستتواصل معك خدمة العملاء لربطك مباشرة مع د. بدر إبراهيم للتنسيق حول مواعيد التدريب."
        ),
        "جاهزين نبدأ رحلتنا 👌🚀"
    ]

def build_approval_messages_by_course(course_key: str, user_info: dict) -> List[str]:
    if course_key == "kids":
        return _msg_kids(user_info)
    elif course_key == "private":
        return _msg_private(user_info)
    elif course_key == "highschool":
        return _msg_highschool(user_info)
    else:  # default → expert
        return _msg_expert(user_info)

async def send_messages_sequence(context: ContextTypes.DEFAULT_TYPE, chat_id: int, messages: List[str]):
    for m in messages:
        if not m:
            continue
        await context.bot.send_message(
            chat_id=chat_id, text=m, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
