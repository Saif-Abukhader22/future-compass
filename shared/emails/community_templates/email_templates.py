from shared.emails.email_components import base_email_template


def post_invitation_template(first_name: str, post_name: str, post_description: str, invitation_link: str) -> str:
    """Generate a post invite template."""
    content = f"""
    <p>Hi {first_name},</p>
    <p>You are invited to join the post "{post_name}" with the following description:</p>
    <div class="highlight-box">
        {post_description}
    </div>
    <p>To accept the invitation, please click the button below to view the post:</p>
    <p style="text-align: center;">
        <a href="{invitation_link}" class="button">View Post</a>
    </p>
    """

    return base_email_template(
        title="Post Invitation",
        content=content
    )


def post_invitation_accepted_template(first_name: str, post_name: str, post_owner_name: str, invitation_link) -> str:
    """Generate a template for when an invitation is accepted."""
    content = f"""
    <p>Hi {first_name},</p>
    <p>Great news! {post_owner_name} has accepted your invitation to join the post "{post_name}".</p>
    <div class="highlight-box">
        <p>You can now access the post and participate in the discussion.</p>
    </div>
    <p style="text-align: center;">
        <a href="{invitation_link}" class="button">Go to Post</a>
    </p>
    """

    return base_email_template(
        title="Invitation Accepted",
        content=content
    )
