from jinja2 import Template, Environment, BaseLoader
from premailer import transform
from typing import Optional
from shared.emails.email_components import  generate_signature, _render_template, base_email_template

# Initialize Jinja2 environment for consistent template rendering
env = Environment(loader=BaseLoader())



def email_verification_template(first_name: str, email_verification_code: str) -> str:
    """Generate an email verification template."""
    content = f"""
    <p>Hi <strong>{first_name}</strong>,</p>
    <p>Thank you for signing up with the TheoSumma platform! To verify your email address, please use the code below:</p>
    <div class="highlight-box" style="text-align:center;font-size:24px;font-weight:bold;">
        {email_verification_code}
    </div>
    <p>If you didn't request this, please ignore this email or contact our support team.</p>
    """
    return _render_template(base_email_template("Email Verification", content))

def email_complete_verification_template(first_name: str) -> str:
    """Generate an email verification completion template."""
    content = f"""
    <p>Hi <strong>{first_name}</strong>,</p>
    <p>Thank you for signing up with the TheoSumma platform! Your email has now been successfully verified.</p>
    <p>You can now access all features of your account. We're excited to have you with us!</p>
    """
    return _render_template(base_email_template("Email Verification Complete", content))

def password_reset_verification_template(first_name: str, reset_code: str) -> str:
    """Generate a password reset template.

    If ``reset_code`` looks like a URL, render a clean "Reset Password" button
    linking to it. Otherwise, render the value as a verification code.
    """
    is_url = isinstance(reset_code, str) and reset_code.strip().lower().startswith(("http://", "https://"))
    if is_url:
        content = f"""
        <p>Hi <strong>{first_name}</strong>,</p>
        <p>We received a request to reset your password. Click the button below to proceed:</p>
        <p style=\"text-align:center;\">
            <a href=\"{reset_code}\" class=\"button\" target=\"_blank\" rel=\"noopener noreferrer\">Reset Password</a>
        </p>
        <p>This link expires in 15 minutes. For your security, do not share it with anyone.</p>
        <p>If you didn't request this password reset, please secure your account immediately.</p>
        """
    else:
        content = f"""
        <p>Hi <strong>{first_name}</strong>,</p>
        <p>We received a request to reset your password. Use the code below to proceed:</p>
        <div class=\"highlight-box\" style=\"text-align:center;font-size:24px;font-weight:bold;\">{reset_code}</div>
        <p>This code expires in 15 minutes. For your security, please do not share this code with anyone.</p>
        <p>If you didn't request this password reset, please secure your account immediately.</p>
        """
    return _render_template(base_email_template("Password Reset Request", content))

def ts_registration_template(first_name: str) -> str:
    """Generate a registration welcome template."""
    content = f"""
    <p>Hi <strong>{first_name}</strong>,</p>
    <p>We're thrilled to welcome you to the TheoSumma Ministry Platform!</p>
    <p>To get started, log in at <a href="https://app.theosumma.com/login">TheoSumma Ministry App</a> using your email and password.</p>
    <p>If you have any questions or need assistance, don't hesitate to reach out to our support team.</p>
    """
    return _render_template(base_email_template("Welcome to TheoSumma Ministry!", content))

def password_changed_successfully_template(first_name: str) -> str:
    """Generate a password changed confirmation template."""
    content = f"""
    <p>Hi <strong>{first_name}</strong>,</p>
    <p>We're writing to let you know that your TheoSumma account password was successfully changed.</p>
    <div class="highlight-box">
        If you didn't make this change, please reset your password immediately and contact our support team.
    </div>
    """
    return _render_template(base_email_template("Password Changed Successfully", content))

def deactivation_account_successfully_template(first_name: str) -> str:
    """Generate an account deactivation confirmation template."""
    content = f"""
    <p>Hi <strong>{first_name}</strong>,</p>
    <p>We've successfully processed your request to deactivate your TheoSumma account.</p>
    <div class="highlight-box">
        If this was a mistake or you'd like to reactivate your account, please contact our support team.
    </div>
    <p>We're sad to see you go and hope to serve you again in the future.</p>
    """
    return _render_template(base_email_template("Account Deactivation Confirmation", content))

def email_changed_successfully_template(first_name: str, new_email: str) -> str:
    """Generate an email changed confirmation template."""
    content = f"""
    <p>Hi <strong>{first_name}</strong>,</p>
    <p>We're writing to confirm that your TheoSumma account email was successfully changed to:</p>
    <div class="highlight-box">
        <strong>{new_email}</strong>
    </div>
    <p>If you didn't make this change, please secure your account immediately and contact our support team.</p>
    """
    return _render_template(base_email_template("Email Address Updated", content))

def email_security_alert_template(first_name: str) -> str:
    """Generate a security alert email template."""
    content = f"""
    <p>Hi <strong>{first_name}</strong>,</p>
    <p>We detected suspicious activity on your TheoSumma account and want to ensure your security.</p>
    <div class="highlight-box" style="border-left-color:#d9534f;">
        <strong>Recommended Actions:</strong>
        <ul>
            <li>Change your password immediately</li>
            <li>Log out from all devices</li>
            <li>Enable two-factor authentication</li>
        </ul>
    </div>
    <p>If you didn't initiate this activity, please contact our support team right away.</p>
    """
    return _render_template(base_email_template("Security Alert - Suspicious Activity Detected", content))

def contact_us_response_template(first_name: str, reply_message: str, user_message: str) -> str:
    content = f"""
    <p>Hi <strong>{first_name}</strong>,</p>
    <p>Thank you for contacting us through the TheoSumma platform.</p>
    <p>We’ve carefully reviewed your message and here is our response:</p>
    <div class="highlight-box">
        {reply_message}
    </div>
    <br>
    <p><strong>Your original message:</strong></p>
    <blockquote style="border-left: 4px solid #ccc; margin: 10px 0; padding-left: 10px;">
        {user_message}
    </blockquote>
    <p>If you have any further questions, feel free to reach out again. We’re happy to assist you!</p>
    <p>Warm regards,<br>The TheoSumma Team</p>
    """
    return _render_template(base_email_template("Response to Your Message", content))


#
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
#


####################################################################################
####################################################################################
####################################################################################
####################################################################################

#
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
# def email_verification_template(first_name: str, email_verification_code: str) -> str:
#     """Generate an email verification template."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; }
#             h1 { color: #0056b3; font-size: 24px; text-align: center; margin-bottom: 20px; }
#             p { margin: 0 0 15px; }
#             .code { font-weight: bold; color: #d9534f; background: #f8d7da; padding: 8px 12px; border-radius: 4px; display: inline-block; }
#             .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Email Verification</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>Thank you for signing up with the TheoSumma platform! To verify your email address, please use the code below:</p>
#             <p class="code">{{ email_verification_code }}</p>
#             <p>If you didn’t request this, please ignore this email or contact support.</p>
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
#         email_verification_code=email_verification_code,
#         signature=generate_signature()
#     )
#
# def email_complete_verification_template(first_name: str) -> str:
#     """Generate an email verification template."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; }
#             h1 { color: #0056b3; font-size: 24px; text-align: center; margin-bottom: 20px; }
#             p { margin: 0 0 15px; }
#             .code { font-weight: bold; color: #d9534f; background: #f8d7da; padding: 8px 12px; border-radius: 4px; display: inline-block; }
#             .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Email Verification DONE</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>Thank you for signing up with the TheoSumma platform! Your email has now been verified.</p>
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
#         signature=generate_signature()
#     )
#
# def password_reset_verification_template(first_name: str, reset_code: str) -> str:
#     """Generate a password reset verification template."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; }
#             h1 { color: #0056b3; font-size: 24px; text-align: center; margin-bottom: 20px; }
#             p { margin: 0 0 15px; }
#             .code { font-weight: bold; color: #d9534f; background: #f8d7da; padding: 8px 12px; border-radius: 4px; display: inline-block; }
#             .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Password Reset Request</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>We received a request to reset your password. Use the code below to proceed:</p>
#             <p class="code">{{ reset_code }}</p>
#             <p>This code expires in 15 minutes. If you didn’t request this, please secure your account or contact support.</p>
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
#         reset_code=reset_code,
#         signature=generate_signature()
#     )
#
# def ts_registration_template(first_name: str) -> str:
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
#             <h1>Welcome to TheoSumma Ministry!</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>We’re thrilled to welcome you to the TheoSumma Ministry Platform!</p>
#             <p>To get started, log in at <a href="https://app.theosumma.com/login">TheoSumma Ministry App</a> using your email and password:</p>
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
#         signature=generate_signature()
#     )
#
# def password_changed_successfully_template(first_name: str) -> str:
#     """Generate a password reset verification template."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; }
#             h1 { color: #0056b3; font-size: 24px; text-align: center; margin-bottom: 20px; }
#             p { margin: 0 0 15px; }
#             .code { font-weight: bold; color: #d9534f; background: #f8d7da; padding: 8px 12px; border-radius: 4px; display: inline-block; }
#             .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Password changed successfully </h1>
#             <p>Hi {{ first_name }},</p>
#             <p>We just wanted to let you know that your password was successfully changed.</p>
#             <p>If you didn’t make this change, please reset your password immediately and contact our support.</p>
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
#         signature=generate_signature()
#     )
#
# def deactivation_account_successfully_template(first_name: str) -> str:
#     """Generate a password reset verification template."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; }
#             h1 { color: #0056b3; font-size: 24px; text-align: center; margin-bottom: 20px; }
#             p { margin: 0 0 15px; }
#             .code { font-weight: bold; color: #d9534f; background: #f8d7da; padding: 8px 12px; border-radius: 4px; display: inline-block; }
#             .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Account Deactivation</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>We just wanted to let you know that your account was successfully deactivated.</p>
#             <p>If this was a mistake or you’d like to reactivate your account, contact us.</p>
#             <p>We’re sad to see you go,</p>
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
#         signature=generate_signature()
#     )
#
# def email_changed_successfully_template(first_name: str, new_email=str) -> str:
#     """Generate a password reset verification template."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; }
#             h1 { color: #0056b3; font-size: 24px; text-align: center; margin-bottom: 20px; }
#             p { margin: 0 0 15px; }
#             .code { font-weight: bold; color: #d9534f; background: #f8d7da; padding: 8px 12px; border-radius: 4px; display: inline-block; }
#             .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Email changed successfully </h1>
#             <p>Hi {{ first_name }},</p>
#             <p>We just wanted to let you know that your Email was successfully changed.</p>
#             <p>the New email is {{ new_email }}</p>
#             <p>If you didn’t make this change, please reset your password immediately and contact our support.</p>
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
#         new_email=new_email,
#         signature=generate_signature()
#     )
#
# def email_security_alert_template(first_name: str) -> str:
#     """Generate a security alert email template for account hack attempt."""
#     template_str = """
#     <html>
#     <head>
#         <style>
#             body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px; }
#             .container { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; }
#             h1 { color: #d9534f; font-size: 24px; text-align: center; margin-bottom: 20px; }
#             p { margin: 0 0 15px; }
#             .alert { font-weight: bold; color: #d9534f; background: #f8d7da; padding: 8px 12px; border-radius: 4px; display: inline-block; }
#             .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Security Alert - Suspicious Activity Detected</h1>
#             <p>Hi {{ first_name }},</p>
#             <p>We noticed suspicious activity on your account. Someone tried to access your account, and we want to ensure your security.</p>
#             <p class="alert">Please log in to your account immediately, change your password, and log out from all devices.</p>
#             <p>We highly recommend enabling two-factor authentication for additional security.</p>
#             <p>If you did not attempt this action, please contact our support team right away.</p>
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
#         signature=generate_signature()
#     )
