from jinja2 import Environment, BaseLoader
from premailer import transform
from shared import shared_settings
# Initialize Jinja2 environment for consistent template rendering
env = Environment(loader=BaseLoader())

def generate_signature() -> str:
    """Generate a consistent email signature."""
    return f"""
    <p>Best Regards,</p>
    <p><strong>The TheoSumma Team</strong></p>
    <hr style="border:0;border-top:2px solid #2a4365;margin:20px 0;width:100%;">    
    <p style="margin:5px 0;"><img src="{shared_settings.LOGO_URL}" alt="TheoSumma" width="120" style="filter: brightness(0) invert(1);"></p>
    <p style="margin:5px 0;"><a href="http://www.theosumma.com" style="color:#ebf8ff;">www.theosumma.com</a></p>
    """

def _render_template(template_str: str, **kwargs) -> str:
    """Render a Jinja2 template with error handling and CSS inlining."""
    try:
        template = env.from_string(template_str)
        rendered = template.render(**kwargs)
        return transform(rendered)  # Inline CSS for email compatibility
    except Exception as e:
        raise ValueError(f"Failed to render email template: {str(e)}")

def base_email_template(title: str, content: str) -> str:
    """Base template for all emails with consistent styling."""
    return f"""
    <html>
    <head>
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                line-height: 1.6; 
                color: #ebf8ff; 
                margin: 0; 
                padding: 0; 
                background-color: #1a365d;
            }}
            .container {{ 
                max-width: 600px; 
                margin: 20px auto; 
                background: #2c5282; 
                border: 1px solid #2a4365; 
                border-radius: 4px; 
                overflow: hidden; 
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header {{ 
                padding: 25px; 
                text-align: center; 
                background-color: #2b6cb0; 
                border-bottom: 1px solid #2a4365;
            }}
            .logo {{ 
                max-height: 50px; 
                filter: brightness(0) invert(1);
            }}
            .content {{ 
                padding: 30px; 
            }}
            h1 {{ 
                color: #ebf8ff; 
                font-size: 22px; 
                text-align: center; 
                margin-top: 0; 
                margin-bottom: 20px; 
            }}
            p {{ 
                margin: 0 0 15px; 
                font-size: 15px; 
                color: #ebf8ff;
            }}
            .highlight-box {{ 
                background-color: #2a4365; 
                border-left: 4px solid #4299e1; 
                padding: 15px; 
                margin: 20px 0; 
                color: #ebf8ff;
            }}
            .button {{ 
                background-color: #4299e1; 
                color: white; 
                padding: 12px 20px; 
                text-decoration: none; 
                border-radius: 4px; 
                display: inline-block; 
                margin: 15px 0; 
                font-weight: bold;
            }}
            .button:hover {{
                background-color: #3182ce;
            }}
            .footer {{ 
                padding: 15px; 
                text-align: center; 
                font-size: 12px; 
                color: #a3bffa; 
                background-color: #2a4365; 
                border-top: 1px solid #2a4365;
            }}
            .signature {{ 
                margin-top: 30px;
                text-align: center;
            }}
            .signature p {{
                margin: 5px 0;
                text-align: center;
            }}
            .signature hr {{
                margin-left: auto;
                margin-right: auto;
                width: 50%;
            }}
            .signature img {{
                display: block;
                margin-left: auto;
                margin-right: auto;
            }}
            a {{
                color: #90cdf4;
                text-decoration: underline;
            }}
            a:hover {{
                color: #63b3ed;
            }}
            ul {{
                margin: 10px 0;
                padding-left: 20px;
            }}
            li {{
                margin-bottom: 8px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="content">
                <h1>{title}</h1>
                {content}
                <div class="signature">
                    {generate_signature()}
                </div>
            </div>
            <div class="footer">
                This is an automated message. Please do not reply directly to this email.
            </div>
        </div>
    </body>
    </html>
    """


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