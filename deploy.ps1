# Deploy Script
$VPS_USER = "root"
$VPS_IP = "72.62.132.37"
$REMOTE_DIR = "/root/paymentbot"

Write-Host "📦 Zipping files..."
Compress-Archive -Path * -DestinationPath deploy.zip -Force

Write-Host "🚀 Uploading to $VPS_IP..."
scp deploy.zip ${VPS_USER}@${VPS_IP}:${REMOTE_DIR}/deploy.zip

Write-Host "🔧 Restarting Bot..."
# 1. Unzip overwrite
# 2. Build new image
# 3. Stop/Remove old container
# 4. Run new container (mounting db and json to persist data)
ssh ${VPS_USER}@${VPS_IP} "cd ${REMOTE_DIR} && unzip -o deploy.zip && docker build -t paymentbot . && docker rm -f paymentbot || true && docker run -d --name paymentbot --restart always --env-file .env -v ${REMOTE_DIR}/bot_state.db:/app/bot_state.db -v ${REMOTE_DIR}/known_users.json:/app/known_users.json paymentbot"

Write-Host "✅ Deployment Complete!"
Remove-Item deploy.zip
