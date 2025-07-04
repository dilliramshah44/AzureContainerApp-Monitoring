#!/usr/bin/env python3

from azure.identity import AzureCliCredential
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
TO_EMAIL = os.getenv("TO_EMAIL", EMAIL)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# === AUTHENTICATE USING AZURE CLI ===
credential = AzureCliCredential()

def send_summary_email(healthy_apps, unhealthy_apps):
    subject = "[Pangea] Container Apps Health Report"
    body = "Dear Pangea Production Team,\n\n"
    body += "Below is the health status of Azure Container Apps across all subscriptions and resource groups:\n\n"

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

    body += "\nThis is an automated report. Please take action if necessary.\n\nRegards,\nMonitoring System\nPangea Platform"

    # Send email
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

def check_all_container_apps():
    sub_client = SubscriptionClient(credential)
    healthy_apps = {}
    unhealthy_apps = {}

    for sub in sub_client.subscriptions.list():
        sub_id = sub.subscription_id
        sub_name = sub.display_name
        print(f"\n📦 Checking Subscription: {sub_name} ({sub_id})")

        try:
            rg_client = ResourceManagementClient(credential, sub_id)
            app_client = ContainerAppsAPIClient(credential, sub_id)

            for rg in rg_client.resource_groups.list():
                rg_name = rg.name
                print(f"  📁 Resource Group: {rg_name}")

                try:
                    apps = app_client.container_apps.list_by_resource_group(rg_name)
                    for app in apps:
                        app_name = app.name
                        try:
                            app_details = app_client.container_apps.get(rg_name, app_name)
                            status = app_details.provisioning_state
                            app_id = f"{sub_name}/{rg_name}/{app_name}"

                            if status in ["Succeeded", "Running"]:
                                print(f"    ✅ {app_id}")
                                healthy_apps[app_id] = status
                            else:
                                print(f"    ⚠️  {app_id}: {status}")
                                unhealthy_apps[app_id] = status

                        except HttpResponseError as e:
                            unhealthy_apps[app_id] = f"Error: {e.message or 'Unknown'}"

                except Exception as e:
                    print(f"  ❌ Failed to list apps in resource group {rg_name}: {e}")

        except Exception as e:
            print(f"❌ Error with subscription {sub_name}: {e}")

    send_summary_email(healthy_apps, unhealthy_apps)

# === MAIN LOOP ===
if __name__ == "__main__":
    while True:
        check_all_container_apps()
        print("⏳ Waiting 2 minutes before next check...\n")
        time.sleep(120)
