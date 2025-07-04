#!/usr/bin/env python3

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import SubscriptionClient, ResourceManagementClient
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

# === AUTHENTICATE VIA SERVICE PRINCIPAL ===
credential = DefaultAzureCredential()

# === SELECT SUBSCRIPTION ===
sub_client = SubscriptionClient(credential)
subscriptions = list(sub_client.subscriptions.list())

print("\n📦 Available Subscriptions:")
for i, sub in enumerate(subscriptions):
    print(f"{i + 1}. {sub.display_name} ({sub.subscription_id})")

sub_index = int(input("🔹 Select a subscription by number: ")) - 1
SUBSCRIPTION_ID = subscriptions[sub_index].subscription_id

# === SELECT RESOURCE GROUP ===
rg_client = ResourceManagementClient(credential, SUBSCRIPTION_ID)
resource_groups = list(rg_client.resource_groups.list())

print("\n📁 Available Resource Groups:")
for i, rg in enumerate(resource_groups):
    print(f"{i + 1}. {rg.name}")

rg_index = int(input("🔹 Select a resource group by number: ")) - 1
RESOURCE_GROUP = resource_groups[rg_index].name

# === INITIALIZE CONTAINER APPS CLIENT ===
client = ContainerAppsAPIClient(credential, SUBSCRIPTION_ID)

# === FUNCTION TO SEND EMAIL REPORT ===
def send_summary_email(healthy_apps, unhealthy_apps):
    subject = "[Pangea] Container Apps Health Report"

    body = "Dear Pangea Production Team,\n\n"
    body += f"Please find below the latest health status of the container apps in Azure resource group '{RESOURCE_GROUP}'.\n\n"

    if healthy_apps:
        body += "✅ Healthy Container Apps:\n"
        for app, status in healthy_apps.items():
            body += f"  - {app}: {status}\n"
    else:
        body += "✅ No healthy apps found.\n"

    body += "\n"

    if unhealthy_apps:
        body += "⚠️ Unhealthy or Problematic Container Apps:\n"
        for app, status in unhealthy_apps.items():
            body += f"  - {app}: {status}\n"
    else:
        body += "🎉 No unhealthy apps detected.\n"

    body += "\nThis is an automated message. Please take action if necessary.\n\n"
    body += "Regards,\nMonitoring System\nPangea Platform"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL
    msg['To'] = TO_EMAIL

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL, EMAIL_PASSWORD)
            server.sendmail(EMAIL, TO_EMAIL, msg.as_string())
            print("📧 Health summary email sent successfully")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# === FUNCTION TO CHECK CONTAINER APP HEALTH ===
def check_container_apps():
    print(f"\n🔍 Monitoring Azure Resource Group: {RESOURCE_GROUP}")

    healthy_apps = {}
    unhealthy_apps = {}

    try:
        apps = client.container_apps.list_by_resource_group(RESOURCE_GROUP)

        for app in apps:
            app_name = app.name

            try:
                app_details = client.container_apps.get(RESOURCE_GROUP, app_name)
                status = app_details.provisioning_state

                if status in ["Succeeded", "Running"]:
                    print(f"✅ {app_name} is up and running")
                    healthy_apps[app_name] = status
                else:
                    print(f"⚠️  {app_name} is in bad state: {status}")
                    unhealthy_apps[app_name] = status

            except HttpResponseError as e:
                print(f"❌ Failed to fetch details for {app_name}: {e.message}")
                unhealthy_apps[app_name] = f"Error: {e.message}"

    except Exception as e:
        print(f"❌ Error accessing resource group '{RESOURCE_GROUP}': {e}")
        return

    send_summary_email(healthy_apps, unhealthy_apps)

# === MAIN LOOP ===
if __name__ == "__main__":
    while True:
        check_container_apps()
        print("⏳ Waiting 2 minutes before next check...\n")
        time.sleep(120)
