# utils/oauth_verification.py
import httpx


from identity_service.config import settings


async def verify_google_token(token: str) -> dict | None:
    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"

    async with httpx.AsyncClient() as client:
        res = await client.get(url)

    if res.status_code != 200:
        return None

    data = res.json()

    if data.get("aud") != settings.GOOGLE_CLIENT_ID:
        return None

    if not data.get("email_verified", False):
        return None

    if data.get("iss") not in ["https://accounts.google.com", "accounts.google.com"]:
        return None

    return {
        "email": data.get("email"),
        "first_name": data.get("given_name"),
        "last_name": data.get("family_name"),
        "profile_picture": data.get("picture"),
    }

async def verify_facebook_token(token: str) -> dict | None:
    app_token = f"{settings.FACEBOOK_APP_ID}|{settings.FACEBOOK_APP_SECRET}"
    debug_url = f"https://graph.facebook.com/debug_token?input_token={token}&access_token={app_token}"

    async with httpx.AsyncClient() as client:
        debug_res = await client.get(debug_url)
        if debug_res.status_code != 200:
            return None
        debug_data = debug_res.json().get("data", {})
        if not debug_data.get("is_valid") or debug_data.get("app_id") != settings.FACEBOOK_APP_ID:
            return None  # Token invalid or not for your app

        # Then fetch user info
        user_url = f"https://graph.facebook.com/me?fields=id,first_name,last_name,email,picture.type(large)&access_token={token}"
        user_res = await client.get(user_url)
        if user_res.status_code != 200:
            return None
        data = user_res.json()
        return {
            "email": data.get("email"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "profile_picture": data.get("picture", {}).get("data", {}).get("url"),
        }

#
# from google.oauth2 import id_token as google_id_token
# from google.auth.transport import requests as google_requests
# from fastapi import HTTPException
# import aiohttp
#
# async def verify_google_token(token: str) -> dict | None:
#     try:
#         idinfo = google_id_token.verify_oauth2_token(token, google_requests.Request())
#         user_info = {
#             "email": idinfo["email"],
#             "first_name": idinfo.get("given_name", ""),
#             "last_name": idinfo.get("family_name", ""),
#             "profile_picture": idinfo.get("picture", ""),
#             "provider_user_id": idinfo["sub"]
#         }
#         return user_info
#     except Exception as e:
#         raise HTTPException(status_code=400, detail="Invalid Google token")
#
#
# async def verify_facebook_token(token: str) -> dict | None:
#         async with aiohttp.ClientSession() as session:
#             async with session.get(
#                 f"https://graph.facebook.com/me?fields=id,first_name,last_name,email,picture&access_token={token}"
#             ) as resp:
#                 if resp.status != 200:
#                     raise HTTPException(status_code=400, detail="Invalid Facebook token")
#                 data = await resp.json()
#                 user_info = {
#                     "email": data["email"],
#                     "first_name": data["first_name"],
#                     "last_name": data["last_name"],
#                     "profile_picture": data["picture"]["data"]["url"],
#                     "provider_user_id": data["id"]
#                 }
#             if not user_info or not user_info.get("email"):
#                 raise HTTPException(status_code=400, detail="Missing user info")
#             return user_info
#
#
# async def verify_facebook_token(token: str) -> dict | None:
#         async with aiohttp.ClientSession() as session:
#             async with session.get(
#                 f"https://graph.facebook.com/me?fields=id,first_name,last_name,email,picture&access_token={token}"
#             ) as resp:
#                 if resp.status != 200:
#                     raise HTTPException(status_code=400, detail="Invalid Facebook token")
#                 data = await resp.json()
#                 user_info = {
#                     "email": data["email"],
#                     "first_name": data["first_name"],
#                     "last_name": data["last_name"],
#                     "profile_picture": data["picture"]["data"]["url"],
#                     "provider_user_id": data["id"]
#                 }
#             if not user_info or not user_info.get("email"):
#                 raise HTTPException(status_code=400, detail="Missing user info")
#             return user_info
