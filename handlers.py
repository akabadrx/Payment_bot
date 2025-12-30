import logging
import html as _html

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
import utils
import db

logger = logging.getLogger(__name__)

# Broadcast control flag
broadcast_cancelled = False

# --- (4) COMMANDS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    utils.save_known_user(chat_id)
    
    # Initialize/Reset user state in DB
    user_state = {"telegram_username": update.effective_user.username}
    db.update_user_state(chat_id, user_state)

    welcome_message = """
أهلاً وسهلاً في عالم تقوية الذاكرة! 🚀

أنا د. بدر إبراهيم - طبيب، مدرب قوى ذاكرة، وبطل تحدي العقل القوي 2025.

سعيد بانضمامك إلينا في هذه الرحلة المدهشة نحو ذاكرة أقوى وتفوق دراسي وعقلي استثنائي.

في منصة الحفظ الذهني، نقدم برامج تدريبية متخصصة تناسب جميع الفئات العمرية، تركز على التطبيق العملي والمتابعة اليومية الحقيقية مع المدرب.

 إليك البرامج المتاحة حالياً:
    """
    keyboard = [
        [InlineKeyboardButton(config.COURSES["expert"]["title"], callback_data="course_expert")],
        [InlineKeyboardButton(config.COURSES["private"]["title"], callback_data="course_private")],
        [InlineKeyboardButton(config.COURSES["kids"]["title"], callback_data="course_kids")],
        [InlineKeyboardButton(config.COURSES["highschool"]["title"], callback_data="course_highschool")],
        [InlineKeyboardButton("💬 التحدث مع خدمة العملاء", callback_data="support")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_message, reply_markup=reply_markup)

# --- (9) ASK PAYMENT METHOD TRIGGER ---
async def ask_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Check if coupon applied
    user_state = db.get_user_state(chat_id)
    discount = user_state.get("discount_percent", 0)
    
    msg_intro = "رائع! يسعدنا جداً انضمامك ✨\nاختر طريقة الدفع المناسبة:"
    if discount > 0:
        msg_intro = f"🎉 **تم تفعيل الخصم بنسبة {discount}%!**\nالآن اختر طريقة الدفع لإتمام العملية بالسعر الجديد:"
        
    keyboard = [
        [InlineKeyboardButton("🎟️ لدي كوبون خصم", callback_data="coupon_request")],
        [InlineKeyboardButton("PayPal", callback_data="pay_paypal")],
        [InlineKeyboardButton("بنكك (السودان)", callback_data="pay_bankak")],
        [InlineKeyboardButton("تحويل بنكي (السعودية)", callback_data="pay_saudi")],
        [InlineKeyboardButton("تحويل بنكي (الإمارات)", callback_data="pay_uae")],
        [InlineKeyboardButton("Western Union / MoneyGram", callback_data="pay_wu_mg")],
        [InlineKeyboardButton("محفظة الهاتف (رواندا)", callback_data="pay_rwanda")],
        [InlineKeyboardButton("فودافون كاش / انستا باي (مصر)", callback_data="pay_vodafone_eg")],
        [InlineKeyboardButton("تحويل بنكي عبر IBAN", callback_data="pay_iban")],
    ]
    await context.bot.send_message(chat_id=chat_id, text=msg_intro, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def ask_payment_method_callback(query, context, user_state):
    """Version for use with callback queries (edits message instead of sending new)"""
    discount = user_state.get("discount_percent", 0)
    
    msg_intro = "رائع! يسعدنا جداً انضمامك ✨\nاختر طريقة الدفع المناسبة:"
    if discount > 0:
        msg_intro = f"🎉 **تم تفعيل الخصم بنسبة {discount}%!**\nالآن اختر طريقة الدفع لإتمام العملية بالسعر الجديد:"
        
    keyboard = [
        [InlineKeyboardButton("🎟️ لدي كوبون خصم", callback_data="coupon_request")],
        [InlineKeyboardButton("PayPal", callback_data="pay_paypal")],
        [InlineKeyboardButton("بنكك (السودان)", callback_data="pay_bankak")],
        [InlineKeyboardButton("تحويل بنكي (السعودية)", callback_data="pay_saudi")],
        [InlineKeyboardButton("تحويل بنكي (الإمارات)", callback_data="pay_uae")],
        [InlineKeyboardButton("Western Union / MoneyGram", callback_data="pay_wu_mg")],
        [InlineKeyboardButton("محفظة الهاتف (رواندا)", callback_data="pay_rwanda")],
        [InlineKeyboardButton("فودافون كاش / انستا باي (مصر)", callback_data="pay_vodafone_eg")],
        [InlineKeyboardButton("تحويل بنكي عبر IBAN", callback_data="pay_iban")],
    ]
    await query.edit_message_text(text=msg_intro, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# --- (4.5) TEXT HANDLER (stages) ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # LOAD STATE
    user_state = db.get_user_state(chat_id)

    if not user_state:
        await update.message.reply_text("يرجى البدء أولاً عبر الأمر /start")
        return

    stage = user_state.get("stage")
    course_selected = user_state.get("course")

    if stage == "awaiting_name":
        user_state["name"] = text
        user_state["stage"] = "awaiting_email"
        db.update_user_state(chat_id, user_state)
        await update.message.reply_text("ممتاز! الآن يرجى إدخال عنوان بريدك الإلكتروني:")

    elif stage == "awaiting_email":
        # General structure check
        if "@" not in text or "." not in text:
            await update.message.reply_text("يرجى إدخال بريد إلكتروني صحيح (مثال: name@example.com):")
            return

        # Special logic for Expert and Highschool courses: must be @gmail.com AND double confirmed
        if course_selected in ["expert", "highschool"]:
            if not text.lower().endswith("@gmail.com"):
                await update.message.reply_text("يرجى إدخال بريد إلكتروني من Gmail فقط (مثال: name@gmail.com):")
                return
            
            # Store temporarily and ask for confirmation
            user_state["temp_email"] = text
            user_state["stage"] = "awaiting_email_confirmation"
            db.update_user_state(chat_id, user_state)
            await update.message.reply_text("لتأكيد البريد الإلكتروني، يرجى كتابته مرة أخرى:")
            return

        # For other courses: accept any valid email structure and proceed
        user_state["email"] = text
        user_state["stage"] = "awaiting_whatsapp"
        db.update_user_state(chat_id, user_state)
        await update.message.reply_text("يرجى إدخال رقم الواتساب مع مفتاح الدولة (مثال: +966500000000):")

    elif stage == "awaiting_email_confirmation":
        first_email = user_state.get("temp_email", "")
        if text.strip().lower() == first_email.strip().lower():
            # Emails match
            user_state["email"] = first_email
            user_state.pop("temp_email", None)
            
            # Proceed to WhatsApp
            user_state["stage"] = "awaiting_whatsapp"
            db.update_user_state(chat_id, user_state)
            await update.message.reply_text("يرجى إدخال رقم الواتساب مع مفتاح الدولة (مثال: +966500000000):")
        else:
            # Mismatch - ask to start over
            user_state["stage"] = "awaiting_email"
            user_state.pop("temp_email", None)
            db.update_user_state(chat_id, user_state)
            await update.message.reply_text("عذراً، البريد الإلكتروني غير متطابق.\nيرجى إدخال البريد الإلكتروني من البداية:")

    elif stage == "awaiting_whatsapp":
        user_state["whatsapp"] = text
        
        # Branch based on course type
        if course_selected == "kids":
            user_state["stage"] = "awaiting_kids_count"
            db.update_user_state(chat_id, user_state)
            await update.message.reply_text("كم عدد الأطفال المسجّلين؟ (اكتب رقماً، مثال: 1 أو 2 أو 3)")
        elif course_selected == "highschool":
            user_state["stage"] = "awaiting_hs_count"
            db.update_user_state(chat_id, user_state)
            await update.message.reply_text("كم عدد المتدربين في البرنامج؟ (اكتب رقماً، مثال: 1 أو 2 أو 3)")
        else:
            user_state["stage"] = "awaiting_payment_choice"
            db.update_user_state(chat_id, user_state)
            await ask_payment_method(update, context)

    elif stage == "awaiting_kids_count":
        # validate integer >0
        try:
            k = int(text)
            if k <= 0:
                raise ValueError()
        except ValueError:
            await update.message.reply_text("من فضلك اكتب عدداً صحيحاً أكبر من صفر. مثال: 1 أو 2 أو 3")
            return
        user_state["kids_count"] = k
        user_state["stage"] = "awaiting_kids_names"
        db.update_user_state(chat_id, user_state)
        await update.message.reply_text("ما هي أسماء الأطفال؟ اكتبها مفصولة بفواصل. مثال: أحمد، سارة")
    elif stage == "awaiting_hs_count":
        # validate integer >0
        try:
            k = int(text)
            if k <= 0:
                raise ValueError()
        except ValueError:
            await update.message.reply_text("من فضلك اكتب عدداً صحيحاً أكبر من صفر. مثال: 1 أو 2 أو 3")
            return
        user_state["hs_count"] = k
        user_state["stage"] = "awaiting_hs_names"
        db.update_user_state(chat_id, user_state)
        await update.message.reply_text("ما هي أسماء المتدربين؟ اكتبها مفصولة بفواصل. مثال: علي، محمد")

    elif stage == "awaiting_kids_names":
        # store names; optional check on count
        names = [n.strip() for n in text.split(",") if n.strip()]
        user_state["kids_names"] = ", ".join(names)
        expected = user_state.get("kids_count", 0)
        if expected and len(names) != expected:
            await update.message.reply_text(
                f"تنبّه: كتبت {len(names)} اسم/أسماء بينما العدد هو {expected}. "
                "لو صحيح اضغط موافق، أو اكتب الأسماء من جديد.\n\nاكتب: موافق  — أو  أعد إدخال الأسماء."
            )
            user_state["stage"] = "confirm_kids_names"
            db.update_user_state(chat_id, user_state)
            return
        # proceed
        user_state["stage"] = "awaiting_payment_choice"
        db.update_user_state(chat_id, user_state)
        await ask_payment_method(update, context)
    elif stage == "awaiting_hs_names":
        names = [n.strip() for n in text.split(",") if n.strip()]
        user_state["hs_names"] = ", ".join(names)
        expected = user_state.get("hs_count", 0)
        if expected and len(names) != expected:
            await update.message.reply_text(
                f"تنبّه: كتبت {len(names)} اسم/أسماء بينما العدد هو {expected}. "
                "لو صحيح اضغط موافق، أو اكتب الأسماء من جديد.\n\nاكتب: موافق  — أو  أعد إدخال الأسماء."
            )
            user_state["stage"] = "confirm_hs_names"
            db.update_user_state(chat_id, user_state)
            return
        user_state["stage"] = "awaiting_payment_choice"
        db.update_user_state(chat_id, user_state)
        await ask_payment_method(update, context)

    elif stage == "confirm_kids_names":
        if text.strip().lower() in ["موافق", "ok", "تمام", "نعم", "yes"]:
            user_state["stage"] = "awaiting_payment_choice"
            db.update_user_state(chat_id, user_state)
            await ask_payment_method(update, context)
        else:
            # treat as new names input
            names = [n.strip() for n in text.split(",") if n.strip()]
            user_state["kids_names"] = ", ".join(names)
            expected = user_state.get("kids_count", 0)
            if expected and len(names) != expected:
                await update.message.reply_text(
                    f"ما زال العدد لا يطابق ({len(names)} اسم مقابل {expected}). "
                    "لو مناسب اكتب: موافق — أو أعد إدخال الأسماء."
                )
                db.update_user_state(chat_id, user_state)
                return
            user_state["stage"] = "awaiting_payment_choice"
            db.update_user_state(chat_id, user_state)
            await ask_payment_method(update, context)
    elif stage == "confirm_hs_names":
        if text.strip().lower() in ["موافق", "ok", "تمام", "نعم", "yes"]:
            user_state["stage"] = "awaiting_payment_choice"
            db.update_user_state(chat_id, user_state)
            await ask_payment_method(update, context)
        else:
            names = [n.strip() for n in text.split(",") if n.strip()]
            user_state["hs_names"] = ", ".join(names)
            expected = user_state.get("hs_count", 0)
            if expected and len(names) != expected:
                await update.message.reply_text(
                    f"ما زال العدد لا يطابق ({len(names)} اسم مقابل {expected}). "
                    "لو مناسب اكتب: موافق — أو أعد إدخال الأسماء."
                )
                db.update_user_state(chat_id, user_state)
                return
            user_state["stage"] = "awaiting_payment_choice"
            db.update_user_state(chat_id, user_state)
            await ask_payment_method(update, context)

    elif stage == "awaiting_amount":
        user_state["amount_paid"] = text
        user_state["stage"] = "completed"
        db.update_user_state(chat_id, user_state)
        await forward_to_admin(update, context)

    elif stage == "awaiting_wu_details":
        user_state["wu_details"] = text
        user_state["stage"] = "completed"
        db.update_user_state(chat_id, user_state)
        await forward_to_admin(update, context)

    elif stage == "awaiting_vodafone_details":
        user_state["vodafone_details"] = text
        user_state["stage"] = "completed"
        db.update_user_state(chat_id, user_state)
        await forward_to_admin(update, context)

    elif stage == "awaiting_coupon":
        # Check for skip first
        if text == "تخطي":
            user_state["stage"] = "awaiting_payment_choice"
            db.update_user_state(chat_id, user_state)
            await ask_payment_method(update, context)
            return
            
        # Validate coupon with user's selected course
        user_course = user_state.get("course")
        discount = db.get_coupon(text, user_course)
        if discount:
            user_state["discount_percent"] = discount
            user_state["coupon_code"] = text.upper()
            user_state["stage"] = "awaiting_payment_choice"
            db.update_user_state(chat_id, user_state)
            await update.message.reply_text(f"✅ كود صحيح! تم تطبيق خصم {discount}% بنجاح.")
            await ask_payment_method(update, context)
        else:
            # Wrong coupon - show error and give payment options with skip button
            skip_btn = [[InlineKeyboardButton("⏭️ تخطي والمتابعة", callback_data="skip_coupon")]]
            await update.message.reply_text(
                "❌ الكوبون غير صحيح أو منتهي الصلاحية.\nيرجى إعادة كتابة الكوبون بالشكل الصحيح أو اضغط على تخطي:",
                reply_markup=InlineKeyboardMarkup(skip_btn)
            )


    else:
        await update.message.reply_text("لست متأكداً مما يجب فعله. ابدأ من جديد باختيار أحد الكورسات: /start")

# --- (7) ADMIN HANDLERS ---
async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Load state
    user_info = db.get_user_state(chat_id)

    if not user_info:
        logger.error(f"Could not forward to admin: user_data for chat_id {chat_id} is missing.")
        return

    await update.message.reply_text("📤 تم استلام كافة المعلومات وجاري مراجعتها. سنقوم بالرد عليك قريباً جداً.")

    try:
        row_index = utils.save_to_google_sheet(user_info)
        user_info["sheet_row"] = row_index
        db.update_user_state(chat_id, user_info)
    except Exception as e:
        for admin_id in config.ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=f"❌ خطأ أثناء الحفظ في Google Sheets للمستخدم {chat_id}: {str(e)}")
            except Exception:
                pass

    course_key = user_info.get("course")
    course_title = config.COURSES.get(course_key, {}).get("title", "غير محدد")

    caption = f"""<b>📩 طلب تسجيل جديد:</b>

👤  الاسم:  <code>{_html.escape(user_info.get('name', 'N/A') or 'N/A')}</code>
📧  الإيميل:  <code>{_html.escape(user_info.get('email', 'N/A') or 'N/A')}</code>
  واتساب:  <code>{_html.escape(user_info.get('whatsapp', 'غير متوفر') or 'غير متوفر')}</code>
📘  الكورس:  {_html.escape(course_title)}
💳  طريقة الدفع:  {_html.escape(user_info.get('payment_method', 'N/A') or 'N/A')}
💰  المبلغ المدفوع:  <code>{_html.escape(user_info.get('amount_paid', 'N/A') or 'N/A')}</code>
🔗  المستخدم:  @{_html.escape(user_info.get('telegram_username', 'N/A') or 'N/A')}
"""

    if course_key == "kids":
        kc = user_info.get("kids_count")
        kn = user_info.get("kids_names")
        if kc or kn:
            caption += f"\n<b>أطفال:</b> عدد = {kc or '-'} | الأسماء: <code>{_html.escape(kn or '')}</code>\n"
    elif course_key == "highschool":
        hc = user_info.get("hs_count")
        hn = user_info.get("hs_names")
        if hc or hn:
            caption += f"\n<b>متدربون:</b> عدد = {hc or '-'} | الأسماء: <code>{_html.escape(hn or '')}</code>\n"

    if user_info.get("wu_details"):
        caption += f"""

<b>تفاصيل Western Union:</b>
<code>{_html.escape(user_info.get('wu_details') or '')}</code>
"""
    if user_info.get("vodafone_details"):
        caption += f"""

<b>تفاصيل فودافون كاش:</b>
<code>{_html.escape(user_info.get('vodafone_details') or '')}</code>
"""

    keyboard = [[InlineKeyboardButton("✅ قبول", callback_data=f"approve_{chat_id}"),
                 InlineKeyboardButton("❌ رفض", callback_data=f"reject_{chat_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        file_id = user_info.get("receipt_file_id")
        if not file_id:
            raise ValueError("File ID for receipt is missing.")

        # Send to all admins
        for admin_id in config.ADMIN_IDS:
            try:
                if user_info.get("receipt_is_photo"):
                    await context.bot.send_photo(
                        chat_id=admin_id, photo=file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup
                    )
                else:
                    await context.bot.send_document(
                        chat_id=admin_id, document=file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup
                    )
            except Exception as admin_err:
                logger.warning(f"Failed to send to admin {admin_id}: {admin_err}")
    except Exception as e:
        logger.error(f"Failed to send receipt notification for user {chat_id}: {e}")
        error_message_for_admin = f"""⚠️ فشل في إرسال إشعار طلب التسجيل للمستخدم {chat_id}.

البيانات:
{caption}
"""
        for admin_id in config.ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=error_message_for_admin, parse_mode=None, reply_markup=reply_markup)
            except Exception:
                pass

# --- (8) RECEIPT HANDLER ---
async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Load state
    user_state = db.get_user_state(chat_id)

    if not user_state or user_state.get("stage") != "awaiting_receipt":
        await update.message.reply_text("يرجى إكمال خطوات التسجيل أولاً قبل إرسال الإيصال. ابدأ من /start")
        return

    file_id = None
    is_photo = False
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        is_photo = True
    elif update.message.document:
        file_id = update.message.document.file_id
        is_photo = False
    else:
        await update.message.reply_text("صيغة الملف غير مدعومة. أرسل الإيصال كصورة (PNG/JPEG) أو ملف PDF.")
        return

    user_state["receipt_file_id"] = file_id
    user_state["receipt_is_photo"] = is_photo
    db.update_user_state(chat_id, user_state)

    payment_method_info = user_state.get("payment_method_info", {})
    if payment_method_info.get("requires_extra_info"):
        method = user_state.get("payment_method", "")
        if "فودافون" in method or "vodafone" in method.lower():
            user_state["stage"] = "awaiting_vodafone_details"
            db.update_user_state(chat_id, user_state)
            await update.message.reply_text(
                "تم استلام الإيصال بنجاح 👍\n"
                "الرجاء إرسال في رسالة واحدة:\n"
                "- الاسم الكامل الذي تم التحويل منه\n"
                "- رقم المحفظة التي تم التحويل منها"
            )
        else:
            user_state["stage"] = "awaiting_wu_details"
            db.update_user_state(chat_id, user_state)
            await update.message.reply_text(
                "تم استلام الإيصال. لإكمال التحقق، أرسل في رسالة واحدة:\n"
                "- الاسم الكامل المستخدم في الحوالة\n"
                "- الدولة التي أرسلت منها\n"
                "- الرقم المرجعي (MTCN or Reference No.)"
            )
    else:
        # Skip the amount step - go directly to admin review
        user_state["stage"] = "completed"
        db.update_user_state(chat_id, user_state)
        await update.message.reply_text("تم استلام الإيصال! 👍\n📤 جاري مراجعة طلبك...")
        await forward_to_admin(update, context)

# --- (10) APPROVAL FLOW (ADMIN DECISION) ---
async def handle_admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, user_chat_id_str = query.data.split("_", 1)
    user_chat_id = int(user_chat_id_str)

    # Load state
    user_info = db.get_user_state(user_chat_id)
    if not user_info:
        await query.answer("❌ بيانات هذا المستخدم غير موجودة (ربما تمت معالجة الطلب).", show_alert=True)
        try:
            await query.edit_message_caption(caption=f"{query.message.caption}\n\n--- ⚠️ تعذر العثور على بيانات الطلب ---")
        except Exception:
            pass
        return

    sheet_row = user_info.get("sheet_row")
    status_msg = ""

    if action == "approve":
        course_key = user_info.get("course", "expert")
        
        # Redeem coupon if used
        coupon_code = user_info.get("coupon_code")
        if coupon_code:
            db.redeem_coupon(coupon_code)

        # لو الكورس هو خبير الذاكرة أو طلاب الثانوية → نعطي صلاحية تلقائياً على فولدر الدرايف
        if course_key == "expert":
            email = (user_info.get("email") or "").strip()
            if email:
                ok = utils.grant_expert_drive_access(email)
                if not ok:
                    # ننبّه الأدمن لو ما قدرنا ندي صلاحية
                    for admin_id in config.ADMIN_IDS:
                        try:
                            await context.bot.send_message(
                                admin_id,
                                f"⚠️ لم يتم منح صلاحية Google Drive تلقائياً للإيميل: {email}.\n"
                                f"يرجى التحقق يدوياً من مشاركة فولدر الكورس."
                            )
                        except Exception:
                            pass
            else:
                for admin_id in config.ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            admin_id,
                            f"⚠️ لا يوجد بريد إلكتروني مسجل لهذا المستخدم ({user_chat_id})، "
                            "لذلك لم يتم منح صلاحية الدرايف تلقائياً."
                        )
                    except Exception:
                        pass
        elif course_key == "highschool":
            email = (user_info.get("email") or "").strip()
            if email:
                ok = utils.grant_highschool_drive_access(email)
                if not ok:
                    for admin_id in config.ADMIN_IDS:
                        try:
                            await context.bot.send_message(
                                admin_id,
                                f"⚠️ لم يتم منح صلاحية Google Drive تلقائياً للإيميل: {email}.\n"
                                f"يرجى التحقق يدوياً من مشاركة فولدر الكورس."
                            )
                        except Exception:
                            pass
            else:
                for admin_id in config.ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            admin_id,
                            f"⚠️ لا يوجد بريد إلكتروني مسجل لهذا المستخدم ({user_chat_id})، "
                            "لذلك لم يتم منح صلاحية الدرايف تلقائياً."
                        )
                    except Exception:
                        pass

        # إرسال رسائل الترحيب / التعليمات حسب نوع الكورس
        msgs = utils.build_approval_messages_by_course(course_key, user_info)
        await utils.send_messages_sequence(context, user_chat_id, msgs)
        status_msg = "✅ Approved"
        await query.answer("✅ تم القبول وإرسال رسالة التأكيد المناسبة.", show_alert=True)
    elif action == "reject":
        rejection_reason = "قد يكون السبب مشكلة في إيصال الدفع أو عدم وضوحه."
        await context.bot.send_message(
            user_chat_id,
            f"❌ تم رفض طلبك. {rejection_reason} يرجى التواصل مع خدمة العملاء للمزيد من المعلومات: {config.CUSTOMER_SUPPORT_USERNAME}",
        )
        status_msg = "❌ Rejected"
        await query.answer("تم الرفض بنجاح.", show_alert=True)

    if sheet_row:
        try:
            utils.update_status_in_sheet(sheet_row, status_msg)
        except Exception as e:
            for admin_id in config.ADMIN_IDS:
                try:
                    await context.bot.send_message(admin_id, f"⚠️ لم يتم تحديث الحالة في Google Sheets للمستخدم {user_chat_id}: {str(e)}")
                except Exception:
                    pass

    try:
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n--- تم التعامل مع الطلب: {status_msg} ---")
    except Exception:
        pass

    # Clean up state after final decision
    db.delete_user_state(user_chat_id)

# --- (5) CALLBACKS (General) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    data = query.data

    # Load state
    user_state = db.get_user_state(chat_id)
    if not user_state:
         # Initialize if empty for some reason (e.g. user clicks button after db checks)
         user_state = {"telegram_username": query.from_user.username}
         # but actually we probably should leave it empty or minimal
         db.update_user_state(chat_id, user_state)

    if data.startswith("course_"):
        course_key = data.split("_")[1]
        user_state["course"] = course_key
        db.update_user_state(chat_id, user_state)
        
        course = config.COURSES[course_key]
        buttons = [
            [InlineKeyboardButton("✅ الانضمام الآن", callback_data=f"join_{course_key}")],
            [InlineKeyboardButton("❓ الأسئلة الشائعة", callback_data=f"faq_{course_key}")],
            [InlineKeyboardButton("💬 خدمة العملاء", callback_data="support")],
            [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="start_over")],
        ]
        await query.edit_message_text(text=course["description"], reply_markup=InlineKeyboardMarkup(buttons), parse_mode=None)

    elif data.startswith("join_"):
        user_state["stage"] = "awaiting_name"
        db.update_user_state(chat_id, user_state)
        await query.edit_message_text("ممتاز! لبدء التسجيل، يرجى إرسال اسمك الكامل:")

    elif data.startswith("faq_"):
        course_key = data.split("_")[1]
        faq_buttons = []
        for i, q in enumerate(config.FAQS[course_key]):
            faq_buttons.append([InlineKeyboardButton(q, callback_data=f"question_{course_key}_{i}")])
        faq_buttons.append([InlineKeyboardButton("🔙 العودة لتفاصيل الكورس", callback_data=f"course_{course_key}")])
        await query.edit_message_text("اختر السؤال الذي يهمك:", reply_markup=InlineKeyboardMarkup(faq_buttons))

    elif data.startswith("question_"):
        parts = data.split("_")
        course_key, q_index = parts[1], int(parts[2])
        question = list(config.FAQS[course_key].keys())[q_index]
        answer = config.FAQS[course_key][question]
        back_button = [[InlineKeyboardButton("🔙 العودة للأسئلة", callback_data=f"faq_{course_key}")]]
        await query.edit_message_text(f"❓  السؤال: \n{question}\n\n💬  الإجابة: \n{answer}", reply_markup=InlineKeyboardMarkup(back_button))

    elif data == "coupon_request":
        user_state["stage"] = "awaiting_coupon"
        db.update_user_state(chat_id, user_state)
        skip_btn = [[InlineKeyboardButton("⏭️ تخطي", callback_data="skip_coupon")]]
        await query.edit_message_text("🎟️ الرجاء إدخال كود الكوبون:", reply_markup=InlineKeyboardMarkup(skip_btn))

    elif data == "skip_coupon":
        user_state["stage"] = "awaiting_payment_choice"
        db.update_user_state(chat_id, user_state)
        await ask_payment_method_callback(query, context, user_state)

    elif data.startswith("pay_"):
        method_key = data.replace("pay_", "")  # 'bankak'/'saudi'/'uae'/'wu_mg'/'rwanda'
        course_key = user_state.get("course")
        discount_percent = user_state.get("discount_percent", 0)

        if not course_key:
            await query.edit_message_text("عذراً، انتهت صلاحية الجلسة. يرجى البدء من جديد: /start")
            return

        # Dynamic payment text with per-course pricing
        payment_text = utils.build_payment_text(
            method_key,
            course_key,
            kids_count=user_state.get("kids_count"),
            hs_count=user_state.get("hs_count"),
            discount_percent=discount_percent
        )

        # Save a human-friendly method tag
        friendly_map = {
            "paypal": "PayPal",
            "bankak": "بنكك (السودان)",
            "saudi": "تحويل بنكي (السعودية)",
            "uae": "تحويل بنكي (الإمارات)",
            "wu_mg": "Western Union / MoneyGram",
            "rwanda": "محفظة الهاتف (رواندا)",
               "vodafone_eg": "فودافون كاش / انستا باي (مصر)",
            "iban": "تحويل بنكي (IBAN)",
        }
        user_state["payment_method"] = friendly_map.get(method_key, method_key)
        user_state["payment_method_info"] = {"text": payment_text, "requires_extra_info": (method_key in ["wu_mg", "vodafone_eg"])
}
        user_state["stage"] = "awaiting_receipt"
        db.update_user_state(chat_id, user_state)
        await query.edit_message_text(payment_text, parse_mode=None)

    elif data.startswith("approve_") or data.startswith("reject_"):
        await handle_admin_decision(update, context)

    elif data == "support":
        await query.message.reply_text(f"للتواصل مع خدمة العملاء مباشرة: {config.CUSTOMER_SUPPORT_USERNAME}")

    elif data == "start_over":
        await start_command(update, context)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global broadcast_cancelled
    
    # السماح فقط للأدمن
    if update.effective_user.id not in config.ADMIN_IDS:
        return

    # نص الرسالة بعد الأمر /broadcast
    message_to_send = " ".join(context.args)
    if not message_to_send:
        await update.message.reply_text("الرجاء كتابة الرسالة بعد الأمر. مثال: `/broadcast أهلاً بكم`")
        return

    known_users = utils.load_known_users()
    sent_count = 0
    failed_count = 0
    broadcast_cancelled = False

    await update.message.reply_text(f"📢 جاري بدء البث إلى {len(known_users)} مستخدم...\nاستخدم /cancel لإيقاف البث.")

    for user_id in known_users:
        if broadcast_cancelled:
            await update.message.reply_text(f"🛑 تم إيقاف البث!\n- أُرسلت إلى: {sent_count}\n- فشل: {failed_count}")
            return
        try:
            await context.bot.send_message(chat_id=user_id, text=message_to_send)
            sent_count += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {user_id}: {e}")
            failed_count += 1

    await update.message.reply_text(
        f"📢 تم إرسال البث!\n\n- أُرسلت إلى: {sent_count} مستخدم\n- فشل الإرسال إلى: {failed_count} مستخدم"
    )

async def broadcast_unpaid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcasts a message only to users who haven't completed registration."""
    if update.effective_user.id not in config.ADMIN_IDS:
        return

    message_to_send = " ".join(context.args)
    if not message_to_send:
        await update.message.reply_text("الرجاء كتابة الرسالة بعد الأمر. مثال: `/broadcast_unpaid عرض خاص!`")
        return

    # Get target users
    target_users = db.get_incomplete_users()
    
    if not target_users:
        await update.message.reply_text("لا يوجد مستخدمين غير مكتملين لإرسال الرسالة لهم.")
        return

    sent_count = 0
    failed_count = 0
    broadcast_cancelled = False

    await update.message.reply_text(f"📢 جاري إرسال العرض لـ {len(target_users)} مستخدم (غير مكتمل)...\nاستخدم /cancel لإيقاف البث.")

    for user_id in target_users:
        if broadcast_cancelled:
            await update.message.reply_text(f"🛑 تم إيقاف البث!\n- أُرسلت إلى: {sent_count}\n- فشل: {failed_count}")
            return
        try:
            await context.bot.send_message(chat_id=user_id, text=message_to_send)
            sent_count += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {user_id}: {e}")
            failed_count += 1

    await update.message.reply_text(
        f"📢 تم الإرسال بنجاح!\n\n- تم الوصول إلى: {sent_count} مستخدم محتمل\n- فشل: {failed_count}"
    )

async def cancel_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel ongoing broadcast"""
    global broadcast_cancelled
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    
    broadcast_cancelled = True
    await update.message.reply_text("🛑 جاري إيقاف البث...")

async def admin_add_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /add_coupon CODE PERCENT [COURSE]"""
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    
    try:
        if len(context.args) < 2:
            raise ValueError()
        code = context.args[0]
        percent = int(context.args[1])
        if percent < 1 or percent > 100:
             await update.message.reply_text("النسبة يجب أن تكون بين 1 و 100.")
             return
        
        # Optional: course-specific coupon
        course_key = None
        if len(context.args) > 2:
            course_key = context.args[2].lower()
             
        db.add_coupon(code, percent, usage_limit=0, course_key=course_key)
        
        course_msg = f" (للكورس: {course_key})" if course_key else " (لجميع الكورسات)"
        await update.message.reply_text(f"✅ تم إضافة الكوبون {code.upper()} بنسبة {percent}%{course_msg}")
    except ValueError:
        await update.message.reply_text("خطأ في الصيغة.\nمثال: `/add_coupon SALE20 20`\nأو: `/add_coupon EXPERT50 50 expert`")

async def admin_add_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /add_gift CODE PERCENT [LIMIT] (Default 1)"""
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    
    try:
        if len(context.args) < 2:
            raise ValueError()
        code = context.args[0]
        percent = int(context.args[1])
        limit = 1
        if len(context.args) > 2:
            limit = int(context.args[2])
            
        if percent < 1 or percent > 100:
             await update.message.reply_text("النسبة يجب أن تكون بين 1 و 100.")
             return
             
        db.add_coupon(code, percent, usage_limit=limit)
        await update.message.reply_text(f"🎁 تم إضافة هدية {code.upper()} بنسبة {percent}% (عدد الاستخدامات: {limit})")
    except ValueError:
        await update.message.reply_text("خطأ في الصيغة. مثال: `/add_gift GL78 100 1`")

async def admin_del_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /del_coupon CODE"""
    if update.effective_user.id not in config.ADMIN_IDS:
        return
        
    if not context.args:
        await update.message.reply_text("اكتب الكود للحذف. مثال: `/del_coupon SALE20`")
        return
        
    code = context.args[0]
    db.delete_coupon(code)
    await update.message.reply_text(f"🗑️ تم حذف الكوبون {code.upper()}")

async def admin_list_coupons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return
        
    coupons = db.list_coupons()
    if not coupons:
        await update.message.reply_text("لا توجد كوبونات نشطة حالياً.")
        return
        
    msg = "🎟️ **الكوبونات النشطة:**\n\n"
    for c, data in coupons.items():
        p = data.get("percent", 0)
        count = data.get("count", 0)
        limit = data.get("limit", 0)
        
        limit_str = "∞" if limit == 0 else str(limit)
        msg += f"- `{c}` -> **{p}%** ({count}/{limit_str} استخدم)\n"
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return

    stats = db.get_stats_counts()
    
    total = stats.get("total", 0)
    courses = stats.get("courses", {})
    
    msg = f"📊 **إحصائيات البوت**\n\n"
    msg += f"👥 إجمالي المستخدمين المسجلين (بدأوا البوت): **{total}**\n\n"
    msg += "📚 **توزيع الكورسات (المختارين):**\n"
    
    if not courses:
        msg += "- لا يوجد بيانات بعد.\n"
    else:
        for c_key, count in courses.items():
            if c_key == "unknown": continue
            c_title = config.COURSES.get(c_key, {}).get("title", c_key)
            msg += f"- {c_title}: **{count}**\n"
            
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def admin_funnel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return

    funnel = db.get_funnel_stats()
    
    # Sort stages by logical order (approximate) could be complex, so just list them by count desc
    sorted_stages = sorted(funnel.items(), key=lambda x: x[1], reverse=True)
    
    msg = f"📉 **تحليل سلوك المستخدمين (Funnel)**\n"
    msg += "أين يتوقف المستخدمون حالياً؟\n\n"
    
    if not sorted_stages:
        msg += "- لا يوجد بيانات بعد.\n"
    else:
        for stage, count in sorted_stages:
            msg += f"📍 {stage}: **{count}**\n"
            
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

# --- (11) JOBS (Abandoned Cart) ---
async def check_abandoned_users_job(context: ContextTypes.DEFAULT_TYPE):
    """Job to check for inactive users and send reminders."""
    # Threshold: 2 hours of inactivity
    active_abandoned = db.get_abandoned_users(hours_threshold=2)
    
    for user_id, data in active_abandoned:
        stage = data.get("stage")
        name = data.get("name", "صديقي")
        
        # Decide message based on stage
        msg = ""
        if stage == "awaiting_payment_choice" or stage == "awaiting_receipt" or stage == "awaiting_amount":
            msg = f"مرحباً {name} 👋\n\nلاحظنا أنك قريب جداً من إتمام التسجيل ولكنك توقفت عند خطوة الدفع. هل واجهت مشكلة؟\n\nنحن هنا لمساعدتك، ويمكنك الدفع بسهولة لإكمال حجز مقعدك اليوم 🚀"
        elif stage == "awaiting_email" or stage == "awaiting_whatsapp":
            msg = f"مرحباً {name} 👋\n\nخطوات بسيطة تفصلك عن الانضمام إلينا! 🌟\nأكمل بياناتك الآن لنضمن لك مكانك في الكورس."
        elif stage == "awaiting_name":
            msg = "أهلاً بك! 👋\nلقد بدأت التسجيل معنا... لا تتردد في إكماله لتكتشف قدرات ذاكرتك الحقيقية! 🧠✨"
        else:
            # Generic
            msg = f"مرحباً {name} 👋\n\nاشتقنا لك! لاحظنا عدم إكمال التسجيل. إذا كان لديك أي استفسار، فريق الدعم جاهز لمساعدتك."
            
        # Add call to action
        msg += "\n\nللاستمرار، اضغط هنا: /start"
        
        try:
            await context.bot.send_message(chat_id=user_id, text=msg)
            # Mark as sent so we don't spam
            db.mark_reminder_sent(user_id)
            logger.info(f"Sent abandonment reminder to {user_id}")
        except Exception as e:
            logger.warning(f"Failed to send reminder to {user_id}: {e}")
            # If blocked, maybe mark as sent anyway or delete? For now just log.
            # We mark as sent to avoid loop error spamming logs.
            try:
                db.mark_reminder_sent(user_id)
            except: pass
