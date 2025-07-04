#!/usr/bin/env python3

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.appcontainers import ContainerAppsAPIClient
from azure.core.exceptions import HttpResponseError

from dotenv import load_dotenv
import os
import smtplib
from email.mime.text import MIMEText
import time

# === LOAD ENV ===
load_dotenv()

EMAIL = os.getenv("EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAIL = os.getenv("TO_EMAIL")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP")

# === AUTHENTICATE VIA SERVICE PRINCIPAL ===
credential = DefaultAzureCredential()

# === INITIALIZE CLIENTS ===
rg_client = ResourceManagementClient(credential, SUBSCRIPTION_ID)
client = ContainerAppsAPIClient(credential, SUBSCRIPTION_ID)

# === FUNCTION TO SEND EMAIL REPORT ===
def send_summary_email(healthy_apps, unhealthy_apps):
    subject = "[Pangea] Container Apps Health Report"

    body = f"Dear Pangea Production Team,\n\nHealth status of the container apps in Azure resource group '{RESOURCE_GROUP}':\n\n"

    if healthy_apps:
        body += "✅ Healthy Apps:\n"
        for app, status in healthy_apps.items():
            body += f"  - {app}: {status}\n"
    else:
        body += "✅ No healthy apps found.\n"

    body += "\n"

    if unhealthy_apps:
        body += "⚠️ Unhealthy Apps:\n"
        for app, status in unhealthy_apps.items():
            body += f"  - {app}: {status}\n"
    else:
        body += "🎉 No unhealthy apps detected.\n"

    body += "\nThis is an automated message.\n\nRegards,\nMonitoring System"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL
    msg['To'] = TO_EMAIL

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL, EMAIL_PASSWORD)
            server.sendmail(EMAIL, TO_EMAIL, msg.as_string())
            print("📧 Email sent successfully")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# === FUNCTION TO CHECK CONTAINER APP HEALTH ===
def check_container_apps():
    print(f"\n🔍 Monitoring Resource Group: {RESOURCE_GROUP}")

    healthy_apps = {}
    unhealthy_apps = {}

    try:
        apps = client.container_apps.list_by_resource_group(RESOURCE_GROUP)

        for app in apps:
            app_name = app.name
            try:
                details = client.container_apps.get(RESOURCE_GROUP, app_name)
                status = details.provisioning_state

                if status in ["Succeeded", "Running"]:
                    print(f"✅ {app_name} is healthy")
                    healthy_apps[app_name] = status
                else:
                    print(f"⚠️ {app_name} is unhealthy: {status}")
                    unhealthy_apps[app_name] = status

            except HttpResponseError as e:
                print(f"❌ Error fetching {app_name}: {e.message}")
                unhealthy_apps[app_name] = f"Error: {e.message}"

    except Exception as e:
        print(f"❌ Error listing apps: {e}")
        return

    send_summary_email(healthy_apps, unhealthy_apps)

# === MAIN LOOP ===
if __name__ == "__main__":
    while True:
        check_container_apps()
        print("⏳ Waiting 2 minutes before next check...\n")
        time.sleep(120)
