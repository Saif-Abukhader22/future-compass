import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email_validator import validate_email, EmailNotValidError

from shared.emails.identity_templates.email_templates import password_reset_verification_template, \
    email_verification_template, email_security_alert_template, deactivation_account_successfully_template, \
    email_changed_successfully_template, password_changed_successfully_template, ts_registration_template, \
    email_complete_verification_template, contact_us_response_template
from shared.emails.community_templates.email_templates import (
    post_invitation_accepted_template,
    post_invitation_template
)

from shared import shared_settings
from shared.emails.subscription_templates.email_templates import email_subscription_cancellation_template, \
    payment_failed_template, payment_success_template, failed_renewal_template, renew_template, plan_template, \
    default_plan_template
from shared.k8s_log_proxy import console
from shared.users_sync.schema import UserRead
from shared.utils.logger import TsLogger

# Initialize logger at module level
logger = TsLogger(__name__)


class Email:
    def __init__(self, user: UserRead):
        self.user = user

    def _send_email(self, subject: str, body: str) -> bool:
        required_settings = [
            shared_settings.ZOHO_EMAIL,
            shared_settings.ZOHO_PASSWORD,
            shared_settings.ZOHO_SMTP_SERVER,
            shared_settings.ZOHO_SMTP_PORT
        ]
        console.log("required_settings:", shared_settings.ZOHO_EMAIL)
        console.log("required_settings:", shared_settings.ZOHO_PASSWORD)
        console.log("required_settings:", shared_settings.ZOHO_SMTP_SERVER)
        console.log("required_settings:", shared_settings.ZOHO_SMTP_PORT)

        if not all(required_settings):
            logger.error("Missing required SMTP configuration settings")
            return False

        # Validate email address
        try:
            socket.setdefaulttimeout(5)
            valid = validate_email(str(self.user.email), check_deliverability=True)
            to_email = valid.normalized
        except EmailNotValidError as e:
            logger.error(f"Invalid email address {self.user.email}: {str(e)}")
            return False
        except socket.timeout:
            logger.warning(f"DNS timeout for {self.user.email}, proceeding without deliverability check")
            valid = validate_email(str(self.user.email), check_deliverability=False)
            to_email = valid.normalized

        # Prepare email message
        msg = MIMEMultipart()
        # TODO: setup Zoho to send from no-reply instead of info
        msg["From"] = shared_settings.ZOHO_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        # Send email with increased timeout and detailed logging
        try:
            port = int(str(shared_settings.ZOHO_SMTP_PORT).strip())
            logger.debug(
                f"SMTP settings: server={shared_settings.ZOHO_SMTP_SERVER}, port={port}, from={shared_settings.ZOHO_EMAIL}")
            logger.debug(
                f"Connecting to SMTP server {shared_settings.ZOHO_SMTP_SERVER}:{port}")
            with smtplib.SMTP_SSL(shared_settings.ZOHO_SMTP_SERVER, port, timeout=60) as server:
                server.login(shared_settings.ZOHO_EMAIL, shared_settings.ZOHO_PASSWORD)
                server.sendmail(shared_settings.ZOHO_EMAIL, to_email, msg.as_string())
            logger.info(f"Email sent successfully to {to_email}")
            try:
                # Also print to stdout for immediate visibility in run console
                print(f"[EMAIL SENT] to: {to_email}")
            except Exception:
                pass
            return True
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email to {self.user.email}: {str(e)}")
            return False
        except socket.error as e:
            logger.error(f"Network error sending email to {self.user.email}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email to {self.user.email}: {str(e)}")
            return False

    #############################identity#############################
    def send_contact_us_response_email(self, reply_message: str, user_message: str) -> bool:
        subject = "TheoSumma Ministry - Response to Your Message"
        body = contact_us_response_template(self.user.first_name, reply_message, user_message)
        return self._send_email(subject=subject, body=body)


    def send_password_reset_email(self, token: str) -> bool:  # Password reset - verification code
        return self._send_email(
            subject="TheoSumma Ministry - Password Reset",
            body=password_reset_verification_template(self.user.first_name, token)
        )

    def send_password_changed_email(self) -> bool:  # Password change notification
        return self._send_email(
            subject="TheoSumma Ministry - Your password has been changed",
            body=password_changed_successfully_template(self.user.first_name)
        )

    def send_registration_email(self, email_verification_code: str) -> bool:  # Registration - confirmation email
        return self._send_email(
            subject="TheoSumma Ministry - Confirm Registration",
            body=email_verification_template(self.user.first_name, email_verification_code)
        )

    def send_complete_verification_email(self) -> bool: # Registration - Email Verification Complete
        return self._send_email(
            subject="TheoSumma Ministry - Email Verification Complete",
            body=email_complete_verification_template(self.user.first_name)
        )

    def send_welcome_email(self) -> bool:  # Welcome email - new registration
        return self._send_email(
            subject="Welcome to TheoSumma Ministry",
            body=ts_registration_template(self.user.first_name)
        )

    def send_email_changed_email(self, new_email: str) -> bool:  # Email change notification
        return self._send_email(
            subject="TheoSumma Ministry - Your email address has been updated",
            body=email_changed_successfully_template(self.user.first_name, new_email)
        )

    def send_deactivation_email(self) -> bool:  # Account deactivation notification
        return self._send_email(
            subject="TheoSumma Ministry - Your account has been deactivated",
            body=deactivation_account_successfully_template(self.user.first_name)
        )

    def send_security_alert_email(self) -> bool: # Security Alert
        return self._send_email(
            subject="TheoSumma Ministry - Security Alert: Suspicious Activity on Your Account",
            body=email_security_alert_template(self.user.first_name)
        )

    #############################subscrripe#############################

    def send_transaction_success_email(self, first_name: str,
                             amount: str,
                             plan: str,
                             merchant_transaction_id: str,
                             next_re_date: str,
                             duration: str,
                             card_type: str = "Card",
                             last4: str = "****",
                             payment_date: str = "",
                             ) -> bool:  # Payment success notification
        subject = f"TheoSumma Ministry - Payment Successful for {plan} Plan"
        body = payment_success_template(first_name, amount, plan, merchant_transaction_id, next_re_date, duration,
                                        card_type, last4,payment_date)
        return self._send_email(subject=subject, body=body)

    def send_renew_subscription_email(self, first_name: str,
                   amount: str,
                   plan: str,
                   merchant_transaction_id: str = "",
                   card_type: str = "Card",
                   last4: str = "****",
                   renewal_date: str = "",
                   next_billing_date: str = "",
                   billing_cycle: str = "Monthly",
                   ) -> bool:  # Subscription renewal notification
        subject = f"TheoSumma Ministry - Subscription Renewed for {plan} Plan"
        body = renew_template(first_name, amount, plan, merchant_transaction_id, card_type, last4, renewal_date,
                              next_billing_date, billing_cycle)
        return self._send_email(subject=subject, body=body)


    def send_default_plan_email(self, first_name: str) -> bool:  # Default plan welcome email
        subject = f"TheoSumma Ministry - Welcome to the Default Plan"
        body = default_plan_template(first_name)
        return self._send_email(subject=subject, body=body)

    def send_subscribed_to_plan_email(self, first_name: str,
                                      plan: str) -> bool:  # Subscription - plan confirmation email
        subject = f"TheoSumma Ministry - Welcome to the {plan} Plan"
        body = plan_template(first_name, plan)
        return self._send_email(subject=subject, body=body)

    def send_failed_renew_subscription_email(self, first_name: str, plan: str) -> bool:  # Renewal failure notification
        subject = f"TheoSumma Ministry - Renewal Failed for {plan} Plan"
        body = failed_renewal_template(first_name, plan)
        return self._send_email(subject=subject, body=body)


    def send_transaction_failed_email(self, first_name: str, amount: str,
                                      plan: str) -> bool:  # Payment failure notification
        subject = f"TheoSumma Ministry - Payment Failed for {plan} Plan"
        body = payment_failed_template(first_name, amount, plan)
        return self._send_email(subject=subject, body=body)

    def send_subscription_cancellation_email(self, plan: str) -> bool:
        return self._send_email(
            subject=f"TheoSumma Ministry - Subscription Cancelled for {plan} Plan",
            body=email_subscription_cancellation_template(self.user.first_name, plan)
        )

    #############################Community#############################


    def send_post_invitation_email(self, post_name: str, post_description: str, invitation_link: str) -> bool:
        return self._send_email(
            subject="TheoSumma Ministry - Post Invitation",
            body=post_invitation_template(self.user.first_name, post_name, post_description, invitation_link)
        )

    def send_post_invitation_accepted_email(self, post_name: str, post_owner_name: str, invitation_link: str) -> bool:
        return self._send_email(
            subject="TheoSumma Ministry - Post Invitation Accepted",
            body=post_invitation_accepted_template(self.user.first_name, post_name, post_owner_name, invitation_link)
        )
