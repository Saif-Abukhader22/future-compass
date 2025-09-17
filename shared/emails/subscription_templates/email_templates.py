from jinja2 import Template, Environment, BaseLoader
from premailer import transform
from typing import Optional
from shared.emails.email_components import  generate_signature, _render_template, base_email_template
# Initialize Jinja2 environment for consistent template rendering
env = Environment(loader=BaseLoader())


def default_plan_template(first_name: str) -> str:
    """Generate a registration welcome template with temporary password."""
    content = f"""
    <p>Hi {first_name},</p>
    <p>Thank you for joining TheoSumma with our Default Plan!</p>
    <p>To get started, log in at <a href="https://app.theosumma.com/login">TheoSumma Ministry App</a> using your email and password.</p>
    <div class="highlight-box">
        <p><strong>Note:</strong> You are now on the Default Plan, which will renew after 30 days.</p>
    </div>
    <p>We're excited to have you with us!</p>
    """
    return _render_template(base_email_template("Welcome to Your Default Plan!", content))

def payment_success_template(
    first_name: str,
    amount: str,
    plan: str,
    merchant_transaction_id: str,
    next_re_date: str,
    duration: str,
    card_type: str = "Card",  # Optional: e.g., "Visa"
    last4: str = "****",      # Optional: last 4 digits of card
    payment_date: str = "",   # Optional: formatted date like "May 26, 2025"
) -> str:
    """Generate a Stripe-style template for successful card transaction."""
    content = f"""
    <p>Hi {first_name},</p>

    <p>We’ve received your payment of <strong>${float(amount):.2f} USD</strong> for the <strong>{plan}</strong> plan on <strong>{payment_date}</strong>.</p>
    <p>You have an <strong>{duration} subscription</strong> that will end on <strong>{next_re_date}</strong>.</p>
    <p>Thank you for your purchase!</p>

    <h3>Payment Details:</h3>
    <ul>
        <li><strong>Amount:</strong> ${float(amount):.2f} USD</li>
        <li><strong>Payment Method:</strong> {card_type} ending in {last4}</li>
        <li><strong>Transaction ID:</strong> {merchant_transaction_id}</li>
        <li><strong>Date:</strong> {payment_date}</li>
    </ul>

    <p>If you have any questions, feel free to contact us.</a>.</p>

    <p>Thanks again,</p>
    <p><strong>The TheoSumma Team</strong></p>
    """
    return _render_template(base_email_template("Payment Confirmation", content))


def payment_failed_template(first_name: str, amount: str, plan: str) -> str:
    """Generate a template for failed card transaction."""
    content = f"""
    <p>Hi {first_name},</p>
    <p>We attempted to charge <strong>${amount:.2f}</strong> for the <strong>{plan}</strong> plan, but the transaction was unsuccessful.</p>
    <div class="highlight-box" style="border-left-color:#d9534f;">
        <p>Please review your payment method and try again to ensure continued access.</p>
        <a href="https://app.theosumma.com/account/billing" class="button">Update Payment Info</a>
    </div>
    <p>If you need help, feel free to contact support.</p>
    """
    return _render_template(base_email_template("Payment Failed", content))

def plan_template(first_name: str, plan: str) -> str:
    """Generate a registration welcome template with subscription details."""
    content = f"""
    <p>Hi {first_name},</p>
    <p>Thank you for subscribing to the {plan} plan on TheoSumma App!</p>
    <p>To get started, log in at <a href="https://app.theosumma.com/login">TheoSumma Ministry App</a> using your email and password.</p>
    <div class="highlight-box">
        <p><strong>Note:</strong> Your subscription is now active on the {plan} Plan, which will renew after 30 days.</p>
    </div>
    <p>We're excited to have you with us!</p>
    """
    return _render_template(base_email_template(f"Welcome to Your {plan} Plan!", content))

def renew_template(
    first_name: str,
    amount: str,
    plan: str,
    merchant_transaction_id: str = "",
    card_type: str = "Card",            # e.g., "Visa"
    last4: str = "****",                # last 4 digits
    renewal_date: str = "",            # e.g., "May 26, 2025"
    next_billing_date: str = "",       # e.g., "June 26, 2025"
    billing_cycle: str = "Monthly",    # e.g., "Monthly" or "Yearly"
) -> str:
    """Generate a Stripe-style template for subscription renewal confirmation."""
    content = f"""
    <p>Hi {first_name},</p>

    <p>Your subscription for the <strong>{plan}</strong> plan has been successfully renewed on <strong>{renewal_date}</strong>.</p>

    <p>We’ve charged <strong>${float(amount):.2f} USD</strong> to your payment method ending in <strong>{last4}</strong>. Your next billing date is <strong>{next_billing_date}</strong>.</p>

    <h3>Subscription Details:</h3>
    <ul>
        <li><strong>Plan:</strong> {plan}</li>
        <li><strong>Amount:</strong> ${float(amount):.2f} USD</li>
        <li><strong>Billing Cycle:</strong> {billing_cycle}</li>
        <li><strong>Payment Method:</strong> {card_type} ending in {last4}</li>
        <li><strong>Transaction ID:</strong> {merchant_transaction_id}</li>
        <li><strong>Renewal Date:</strong> {renewal_date}</li>
    </ul>

    <p>Thank you for staying with us!</p>
    """
    return _render_template(base_email_template("Subscription Renewal Confirmation", content))

def failed_renewal_template(first_name: str, plan: str) -> str:
    """Generate a registration welcome template with temporary password."""
    content = f"""
    <p>Hi {first_name},</p>
    <p>We tried to renew your subscription for the <strong>{plan}</strong> plan, but unfortunately, the payment did not go through.</p>
    <div class="highlight-box" style="border-left-color:#d9534f;">
        <p>This might be due to an issue with your payment method.</p>
        <p>To avoid any interruptions in your access, please update your payment details:</p>
        <a href="https://app.theosumma.com/account/billing" class="button">Update Payment Info</a>
    </div>
    <p>In the meantime, you've been switched to the <strong>Free Plan</strong>.</p>
    <p>If you have any questions, our support team is here to help.</p>
    """
    return _render_template(base_email_template("Subscription Renewal Failed", content))

def email_subscription_cancellation_template(first_name: str, plan: str) -> str:
    """Generate an email template for subscription cancellation."""
    content = f"""
    <p>Hi {first_name},</p>
    <p>We wanted to confirm that your subscription for the {plan} plan has been successfully cancelled.</p>
    <div class="highlight-box">
        <p>We're sorry to see you go! If there's anything we can do to improve or if you'd like to re-subscribe in the future, please don't hesitate to reach out.</p>
    </div>
    <p>Thank you for being part of TheoSumma Ministry.</p>
    """
    return _render_template(base_email_template("Subscription Cancellation Confirmation", content))

# def generate_signature() -> str:
#     """Generate a consistent email signature."""
#     return """
#     <p>Best Regards,</p>
#     <p><strong>The TheoSumma Team</strong></p>
#     <hr style="border:0;border-top:1px solid #e0e0e0;margin:20px 0;">
#     <p style="margin:5px 0;"><img src="https://cdn.theosumma.com/public/images/agents/LOGO.png" alt="TheoSumma" width="120"></p>
#     <p style="margin:5px 0;color:#777;">A Ministry Platform</p>
#     <p style="margin:5px 0;color:#777;">123 Ministry Ave, City, State ZIP</p>
#     <p style="margin:5px 0;"><a href="http://www.theosumma.com" style="color:#2c3e50;">www.theosumma.com</a></p>
#     """
#
# def _render_template(template_str: str, **kwargs) -> str:
#     """Render a Jinja2 template with error handling and CSS inlining."""
#     try:
#         template = env.from_string(template_str)
#         rendered = template.render(**kwargs)
#         return transform(rendered)  # Inline CSS for email compatibility
#     except Exception as e:
#         raise ValueError(f"Failed to render email template: {str(e)}")
#
# def base_email_template(title: str, content: str) -> str:
#     """Base template for all emails with consistent styling."""
#     return f"""
#     <html>
#     <head>
#         <style>
#             body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f9f9f9; }}
#             .container {{ max-width: 600px; margin: 20px auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 4px; overflow: hidden; }}
#             .header {{ padding: 25px; text-align: center; background-color: #f5f5f5; border-bottom: 1px solid #e0e0e0; }}
#             .logo {{ max-height: 50px; }}
#             .content {{ padding: 30px; }}
#             h1 {{ color: #2c3e50; font-size: 22px; text-align: center; margin-top: 0; margin-bottom: 20px; }}
#             p {{ margin: 0 0 15px; font-size: 15px; }}
#             .highlight-box {{ background-color: #f5f5f5; border-left: 4px solid #2c3e50; padding: 15px; margin: 20px 0; }}
#             .button {{ background-color: #2c3e50; color: white; padding: 12px 20px; text-decoration: none; border-radius: 4px; display: inline-block; margin: 15px 0; }}
#             .footer {{ padding: 15px; text-align: center; font-size: 12px; color: #777; background-color: #f5f5f5; border-top: 1px solid #e0e0e0; }}
#             .signature {{ margin-top: 30px; }}
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <div class="header">
#                 <img src="https://cdn.theosumma.com/public/images/agents/LOGO.png" alt="TheoSumma Logo" class="logo">
#             </div>
#             <div class="content">
#                 <h1>{title}</h1>
#                 {content}
#                 <div class="signature">
#                     {generate_signature()}
#                 </div>
#             </div>
#             <div class="footer">
#                 This is an automated message. Please do not reply directly to this email.
#             </div>
#         </div>
#     </body>
#     </html>
#     """


####################################################################################
####################################################################################
####################################################################################
####################################################################################

# def generate_signature() -> str:
#     """Generate a consistent email signature."""
#     return "TheoSumma Team"
#
# def _render_template(template_str: str, **kwargs) -> str:
#     """Render a Jinja2 template with error handling and CSS inlining."""
#     try:
#         template = env.from_string(template_str)
#         rendered = template.render(**kwargs)
#         return transform(rendered)  # Inline CSS for email compatibility
#     except Exception as e:
#         raise ValueError(f"Failed to render email template: {str(e)}")
#
#
# def default_plan_template(first_name: str) -> str:
#     """Generate a registration welcome template with temporary password."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; }
#             h1 { color: #0056b3; font-size: 24px; text-align: center; margin-bottom: 20px; }
#             p { margin: 0 0 15px; }
#             a { color: #0056b3; text-decoration: none; }
#             a:hover { text-decoration: underline; }
#             .password { font-weight: bold; color: #d9534f; background: #f8d7da; padding: 8px 12px; border-radius: 4px; display: inline-block; }
#             .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Welcome to Your Default Plan!</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>Thank you for joining TheoSumma with our Default Plan!</p>
#             <p>To get started, log in at <a href="https://app.theosumma.com/login">TheoSumma Ministry App</a> using your email and password:</p>
#             <p><strong>Note:</strong> You are now on the Default Plan, which will renew after 30 days.</p>
#             <p>Best regardsThanks for being with us!</p>
#             <p>Best regards,</p>
#             <p>{{ signature }}</p>
#         </div>
#         <div class="footer">This is an automated email. Please do not reply.</div>
#     </body>
#     </html>
#     """
#     return _render_template(
#         template_str,
#         first_name=first_name,
#         signature=generate_signature()  # Use a consistent signature
#     )
#
# def payment_success_template(first_name: str, amount: str, plan: str, merchant_transaction_id: str = "") -> str:
#     """Generate a template for successful card transaction."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e0e0e0; padding: 20px; }
#             h1 { color: #28a745; font-size: 24px; text-align: center; }
#             p { margin-bottom: 15px; }
#             .footer { margin-top: 20px; font-size: 12px; text-align: center; color: #777; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Payment Successful</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>Your payment of <strong>${{ amount }}</strong> for the <strong>{{ plan }}</strong> plan was successful.</p>
#             <p>You now have full access to TheoSumma’s {{ plan }} content and features.</p>
#             <p><strong>Your Payment on The merchant transaction id: {{ merchant_transaction_id }}</strong></p>
#             <p>Thank you for being with us!</p>
#             <p>Best regards,</p>
#             <p>{{ signature }}</p>
#         </div>
#         <div class="footer">This is an automated email. Please do not reply.</div>
#     </body>
#     </html>
#     """
#     return _render_template(
#         template_str,
#         first_name=first_name,
#         amount=f"{amount:.2f}",
#         plan=plan,
#         merchant_transaction_id=merchant_transaction_id,
#         signature=generate_signature()  # Use a consistent signature
#     )
#
# def payment_failed_template(first_name: str, amount: str, plan: str) -> str:
#     """Generate a template for failed card transaction."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e0e0e0; padding: 20px; }
#             h1 { color: #dc3545; font-size: 24px; text-align: center; }
#             p { margin-bottom: 15px; }
#             a { color: #0056b3; text-decoration: none; }
#             a:hover { text-decoration: underline; }
#             .footer { margin-top: 20px; font-size: 12px; text-align: center; color: #777; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Payment Failed</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>We attempted to charge <strong>${{ amount }}</strong> for the <strong>{{ plan }}</strong> plan, but the transaction was unsuccessful.</p>
#             <p>Please review your payment method and try again to ensure continued access.</p>
#             <p>
#                 <a href="https://app.theosumma.com/account/billing">Update Payment Info</a>
#             </p>
#             <p>If you need help, feel free to contact support.</p>
#             <p>Best regards,</p>
#             <p>{{ signature }}</p>
#         </div>
#         <div class="footer">This is an automated email. Please do not reply.</div>
#     </body>
#     </html>
#     """
#     return _render_template(
#         template_str,
#         first_name=first_name,
#         amount=f"{amount:.2f}",
#         plan=plan,
#         signature=generate_signature()  # Use a consistent signature
#     )
#
#
#
# def plan_template(first_name: str, plan: str) -> str:
#     """Generate a registration welcome template with subscription details."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; }
#             h1 { color: #0056b3; font-size: 24px; text-align: center; margin-bottom: 20px; }
#             p { margin: 0 0 15px; }
#             a { color: #0056b3; text-decoration: none; }
#             a:hover { text-decoration: underline; }
#             .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Welcome to Your {{ plan }} Plan!</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>Thank you for subscribing to the {{ plan }} plan on TheoSumma App!</p>
#             <p>To get started, log in at <a href="https://app.theosumma.com/login">TheoSumma Ministry App</a> using your email and password.</p>
#             <p><strong>Note:</strong> Your subscription is now active on the {{ plan }} Plan, which will renew after 30 days.</p>
#             <p>Thanks for being with us!</p>
#             <p>Best regards,</p>
#             <p>{{ signature }}</p>
#         </div>
#         <div class="footer">This is an automated email. Please do not reply.</div>
#     </body>
#     </html>
#     """
#     return _render_template(
#         template_str,
#         first_name=first_name,
#         plan=plan,
#         signature=generate_signature()  # Use a consistent signature
#     )
#
# def renew_template(first_name: str, amount: str, plan: str, merchant_transaction_id: str = "") -> str:
#     """Generate a template for subscription renewal confirmation."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; }
#             h1 { color: #0056b3; font-size: 24px; text-align: center; margin-bottom: 20px; }
#             p { margin: 0 0 15px; }
#             .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Your Subscription Has Been Renewed!</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>Thank you for renewing your subscription to the <strong>{{ plan }}</strong> plan on the TheoSumma App!</p>
#             <p>Your subscription is now active and will renew again in 30 days unless canceled before that time.</p>
#             <p>Your payment of <strong>{{ amount }}</strong> for the <strong>{{ plan }}</strong> plan was successful.</p>
#             <p><strong>Your Payment on The merchant transaction id: {{ merchant_transaction_id }}</strong></p>
#             <p>If you have any questions, feel free to contact our support team.</p>
#             <p>Best regards,</p>
#             <p>{{ signature }}</p>
#         </div>
#         <div class="footer">This is an automated email. Please do not reply.</div>
#     </body>
#     </html>
#     """
#     return _render_template(
#         template_str,
#         first_name=first_name,
#         plan=plan,
#         amount=amount,
#         merchant_transaction_id=merchant_transaction_id,
#         signature=generate_signature()  # Use a consistent signature
#     )
#
# def failed_renewal_template(first_name: str, plan: str) -> str:
#     """Generate a registration welcome template with temporary password."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; }
#             h1 { color: #0056b3; font-size: 24px; text-align: center; margin-bottom: 20px; }
#             p { margin: 0 0 15px; }
#             a { color: #0056b3; text-decoration: none; }
#             a:hover { text-decoration: underline; }
#             .password { font-weight: bold; color: #d9534f; background: #f8d7da; padding: 8px 12px; border-radius: 4px; display: inline-block; }
#             .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Renewal Failed for Your {{ plan }} Plan</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>We tried to renew your subscription for the <strong>{{ plan }}</strong> plan on the TheoSumma App, but unfortunately, the payment did not go through.</p>
#             <p>This might be due to an issue with your payment method.</p>
#             <p>To avoid any interruptions in your access, please update your payment details and retry the renewal process.</p>
#             <p>
#                 <a href="https://app.theosumma.com/account/billing" class="btn">Update Payment Info</a>
#             </p>
#             <p>In the meantime, you’ve been switched to the <strong>Free Plan</strong>.</p>
#             <p>If you have any questions, our support team is here to help.</p>
#             <p>Best regards,</p>
#             <p>{{ signature }}</p>
#         </div>
#         <div class="footer">This is an automated email. Please do not reply.</div>
#     </body>
#     </html>
#     """
#     return _render_template(
#         template_str,
#         first_name=first_name,
#         plan=plan,
#         signature=generate_signature()
#     )
#
# def email_subscription_cancellation_template(first_name: str, plan: str) -> str:
#     """Generate an email template for subscription cancellation."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; }
#             h1 { color: #d9534f; font-size: 24px; text-align: center; margin-bottom: 20px; }
#             p { margin: 0 0 15px; }
#             .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Subscription Cancellation Confirmation</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>We wanted to confirm that your subscription for the {{ plan }} plan has been successfully cancelled.</p>
#             <p>We’re sorry to see you go! If there’s anything we can do to improve or if you’d like to re-subscribe in the future, please don’t hesitate to reach out to our support team.</p>
#             <p>Thank you for being part of TheoSumma Ministry.</p>
#             <p>Best regards,</p>
#             <p>{{ signature }}</p>
#         </div>
#         <div class="footer">This is an automated email. Please do not reply.</div>
#     </body>
#     </html>
#     """
#     return _render_template(
#         template_str,
#         first_name=first_name,
#         plan=plan,
#         signature=generate_signature()
#     )
#
#
#
