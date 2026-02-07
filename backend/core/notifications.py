"""
Telegram notification service.
"""
import httpx
from typing import List
from config import settings


async def send_telegram_message(chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
    """Send a message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{settings.bot_hub_token}/sendMessage"

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        })

    return response.status_code == 200


async def notify_admin_new_request(
    admin_telegram_id: int,
    requester_name: str,
    org_name: str
) -> bool:
    """Notify admin that someone requested to join their organization."""
    text = (
        f"<b>New Access Request</b>\n\n"
        f"<b>{requester_name}</b> wants to join <b>{org_name}</b>.\n\n"
        f"Open the app to review and approve their request."
    )
    return await send_telegram_message(admin_telegram_id, text)


async def notify_user_approved(
    user_telegram_id: int,
    org_name: str,
    bot_names: List[str]
) -> bool:
    """Notify user that their request was approved."""
    if bot_names:
        bots_text = ", ".join(bot_names)
        text = (
            f"<b>Access Granted!</b>\n\n"
            f"You've been added to <b>{org_name}</b>.\n\n"
            f"You now have access to: <b>{bots_text}</b>"
        )
    else:
        text = (
            f"<b>Access Granted!</b>\n\n"
            f"You've been added to <b>{org_name}</b>.\n\n"
            f"The admin hasn't granted you access to any agents yet."
        )

    return await send_telegram_message(user_telegram_id, text)


async def notify_user_rejected(
    user_telegram_id: int,
    org_name: str
) -> bool:
    """Notify user that their request was rejected."""
    text = (
        f"Your request to join <b>{org_name}</b> was not approved.\n\n"
        f"Please contact the organization admin for more information."
    )
    return await send_telegram_message(user_telegram_id, text)


async def send_journal_reminder(
    user_telegram_id: int,
    business_name: str,
    message: str
) -> bool:
    """Send a journal follow-up reminder to a user."""
    text = (
        f"<b>Follow-up Reminder</b>\n\n"
        f"{message}\n\n"
        f"<i>Lead: {business_name}</i>"
    )
    return await send_telegram_message(user_telegram_id, text)


async def send_invite_link_to_admin(
    admin_telegram_id: int,
    org_name: str,
    invite_code: str,
    app_url: str,
    expires_in_hours: int = 24
) -> bool:
    """
    Send a beautifully formatted invite message to the admin.
    The admin can forward this message to invite users.
    Includes a copy button for easy invite code copying.
    """
    text = (
        f"<b>Invite Link for {org_name}</b>\n\n"
        f"Forward this message to invite team members to your organization.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Step 1:</b> Tap the button below to copy the invite code\n\n"
        f"<b>Step 2:</b> Open the app and tap 'Join with Invite Code'\n\n"
        f"<b>Step 3:</b> Paste the code and submit your request\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<i>This code expires in {expires_in_hours} hours.</i>"
    )

    # Inline keyboard with copy button (Telegram Bot API 7.0+)
    reply_markup = {
        "inline_keyboard": [[
            {
                "text": "Copy Invite Code",
                "copy_text": {
                    "text": invite_code
                }
            }
        ], [
            {
                "text": "Open App",
                "url": app_url
            }
        ]]
    }

    url = f"https://api.telegram.org/bot{settings.bot_hub_token}/sendMessage"

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={
            "chat_id": admin_telegram_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        })

    return response.status_code == 200
