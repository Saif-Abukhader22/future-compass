from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from identity_service.DB.models.users import ContactUsSubmission, User
from identity_service.schemas import user as user_schema
from identity_service.schemas.user import UserRead
from identity_service.services.auth import get_user_by_id
from shared.emails.email import Email


async def add_contact_submission(user:User, db: AsyncSession, data: user_schema.ContactUsCreate):

    new_submission = ContactUsSubmission(
        message= data.message,
        user_id = user.user_id
    )
    if data.phone_number:
        user.phone_number = data.phone_number

    db.add(new_submission)
    await db.commit()
    await db.refresh(new_submission)

    return new_submission

async def reply_message(submission: ContactUsSubmission, response_data: user_schema.ContactUsResponse, db: AsyncSession )-> bool:
        submission_user = await get_user_by_id(db=db, user_id=submission.user_id)

        ############ Send Email ################
        user_read = UserRead.model_validate(submission_user)
        email_service = Email(user_read)
        email_service.send_contact_us_response_email(reply_message=response_data.response, user_message=submission.message)
        return True

async def get_all_submissions(db: AsyncSession):
    all_submissions = await db.execute(select(ContactUsSubmission).order_by(ContactUsSubmission.created_at.desc()))
    return all_submissions.scalars().all()


async def get_submission(sub_id: UUID, db: AsyncSession):
    db_submission = await db.execute(select(ContactUsSubmission).where(ContactUsSubmission.id == sub_id)
                                       .order_by(ContactUsSubmission.created_at.desc()))
    return db_submission.scalars().first()
