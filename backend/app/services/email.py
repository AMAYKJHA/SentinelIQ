import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.dto import EmailSchema


BREVO_URL = settings.BREVO_URL
BREVO_API_KEY = settings.BREVO_API_KEY

async def send_email(email: EmailSchema):
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json",
    }

    payload = {
        "sender": {
            "name": settings.BREVO_FROM_NAME,
            "email": settings.BREVO_FROM_EMAIL
        },
        "to": [
            {
                "email": email.to_email
            }
        ],
        "subject": email.subject,
        "htmlContent": email.html_content,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            BREVO_URL,
            json=payload,
            headers=headers
        )

    if response.status_code != 201:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.json()
        )

    return {
        "message": "Email sent successfully"
    }