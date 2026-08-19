import os
import re
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Union, Optional
from contextlib import asynccontextmanager

import requests
from dateutil.relativedelta import relativedelta
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram.client import Client
from pyrogram.types import User, Chat, ChatPreview, ChatPhoto
from pyrogram.errors import PeerIdInvalid, FloodWait, RPCError
from pyrogram.raw import functions, types



KURIGRAM_AVAILABLE = False

from config import SYS_VAL_X1, SYS_VAL_X2, SYS_VAL_X3, _d

API_ID = int(os.environ.get("API_ID", _d(SYS_VAL_X1)))
API_HASH = os.environ.get("API_HASH", _d(SYS_VAL_X2))
BOT_TOKEN = os.environ.get("BOT_TOKEN", _d(SYS_VAL_X3))


# ─────────────────────────────────────────────
# 🔧 CONFIG & INITIALISATION
# ─────────────────────────────────────────────

IS_VERCEL = bool(os.environ.get("VERCEL"))
TEMP_IMAGES_DIR = "/tmp/temp_images" if (IS_VERCEL or os.environ.get("RAILWAY_ENVIRONMENT")) else "temp_images"

os.makedirs(TEMP_IMAGES_DIR, exist_ok=True)

bot = Client(
    "telegram_info_checker",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    sleep_threshold=10,
    workdir="/tmp" if IS_VERCEL else "."
)

client_lock = asyncio.Lock()

async def ensure_bot_started():
    """Ensure Pyrogram bot client is started safely across serverless invocations."""
    if not getattr(bot, 'is_connected', False):
        async with client_lock:
            if not getattr(bot, 'is_connected', False):
                try:
                    await bot.start()
                except FloodWait as e:
                    print(f"Pyrogram FloodWait: {e.value}s")
                    raise HTTPException(
                        status_code=429,
                        detail=f"Telegram API Rate Limit (FloodWait): Telegram requested a wait of {e.value} seconds."
                    )
                except Exception as e:
                    print(f"Error starting Pyrogram bot client: {e}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Bot Client Connection Error: {str(e)}"
                    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await ensure_bot_started()
    except Exception as e:
        print(f"Error starting Pyrogram bot client: {e}")
    yield
    if getattr(bot, 'is_connected', False):
        try:
            await bot.stop()
        except Exception:
            pass

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # "*" মানে যেকোনো সোর্স থেকে রিকোয়েস্ট এক্সেপ্ট করবে
    allow_credentials=True,   # কুকিজ বা ক্রেডেনশিয়ালস এলাউ করবে
    allow_methods=["*"],      # সব মেথড (GET, POST, PUT, DELETE ইত্যাদি) এলাউ করবে
    allow_headers=["*"],      # সব ধরনের হেডার এলাউ করবে
)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/temp_images", StaticFiles(directory=TEMP_IMAGES_DIR), name="temp_images")


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return Path("static/index.html").read_text(encoding="utf-8")

# ─────────────────────────────────────────────
# 🗺️ DATA-CENTER LOCATION MAP
# ─────────────────────────────────────────────

DC_LOCATIONS = {
    1: "MIA, Miami, USA, US", 2: "AMS, Amsterdam, Netherlands, NL", 3: "SFO, San Francisco, USA, US",
    4: "GRU, São Paulo, Brazil, BR", 5: "DME, Moscow, Russia, RU", 7: "SIN, Singapore, SG",
    8: "FRA, Frankfurt, Germany, DE", 9: "IAD, Washington DC, USA, US", 10: "BLR, Bangalore, India, IN",
    11: "TYO, Tokyo, Japan, JP", 12: "BOM, Mumbai, India, IN", 13: "HKG, Hong Kong, HK",
    14: "MAD, Madrid, Spain, ES", 15: "CDG, Paris, France, FR", 16: "MEX, Mexico City, Mexico, MX",
    17: "YYZ, Toronto, Canada, CA", 18: "MEL, Melbourne, Australia, AU", 19: "DEL, Delhi, India, IN",
    20: "JFK, New York, USA, US", 21: "LHR, London, UK, GB"
}

# ─────────────────────────────────────────────
# 🛠️ HELPER FUNCTIONS
# ─────────────────────────────────────────────

async def get_user_bio(user_id_or_username: Union[int, str]) -> str:
    """Get user bio information"""
    try:
        # First get the basic user info
        user = await bot.get_users(user_id_or_username)

        # Now get full user info including bio using resolve_peer
        try:
            peer = await bot.resolve_peer(user.id)
            full_user = await bot.invoke(
                functions.users.GetFullUser(id=peer)
            )
            bio = full_user.full_user.about or "No bio available"
            return bio
        except Exception as e:
            # If GetFullUser fails, try alternative method
            try:
                # Alternative method using get_chat
                chat = await bot.get_chat(user.id)
                bio = getattr(chat, 'bio', None) or "No bio available"
                return bio
            except Exception as chat_error:
                return f"Bio not available: {str(chat_error)}"

    except Exception as e:
        return f"Error getting user bio: {str(e)}"

async def get_bot_bio(bot_username: str) -> str:
    """Get bot bio information"""
    try:
        user = await bot.get_users(bot_username)
        return await get_user_bio(bot_username)
    except Exception as e:
        return f"Error getting bot bio: {str(e)}"

async def delete_image_after_delay(filepath: str, delay: int = 45):
    await asyncio.sleep(delay)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception:
        pass

async def upload_to_tmpfiles(file_path: str) -> str:
    try:
        url = "https://tmpfiles.org/api/v1/upload"

        with open(file_path, 'rb') as f:
            files = {'file': f}
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.post(url, files=files)
            )

        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('status') == 'success':
                page_url = response_data.get('data', {}).get('url', '')
                if page_url:
                    try:
                        page_resp = await loop.run_in_executor(
                            None,
                            lambda: requests.get(page_url, timeout=5)
                        )
                        if page_resp.status_code == 200:
                            is_video = file_path.lower().endswith(('.mp4', '.webm')) or 'animated' in file_path.lower()
                            
                            if is_video:
                                match = re.search(r'class=["\']download["\']\s+href=["\']([^"\']+)["\']', page_resp.text) or \
                                        re.search(r'<video[^>]+src=["\']([^"\']+)["\']', page_resp.text) or \
                                        re.search(r'href=["\'](https://tmpfiles\.org/dl/[^"\']+\.(?:mp4|webm))["\']', page_resp.text)
                            else:
                                match = re.search(r'class=["\']download["\']\s+href=["\']([^"\']+)["\']', page_resp.text) or \
                                        re.search(r'id=["\']img_preview["\']\s+src=["\']([^"\']+)["\']', page_resp.text)

                            if match:
                                direct_dl_url = match.group(1)
                                if direct_dl_url.startswith("http"):
                                    return direct_dl_url
                    except Exception as scrape_err:
                        print(f"Error scraping tmpfiles page for direct link: {scrape_err}")

                    if '/dl/' not in page_url:
                        page_url = page_url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')
                    return page_url
            else:
                return f"tmpfiles upload failed: {response_data.get('message', 'Unknown error')}"
        else:
            return f"tmpfiles request failed with status code {response.status_code}"
    except Exception as e:
        return f"Error uploading to tmpfiles: {str(e)}"



def is_real_bot(user: User) -> bool:
    return getattr(user, "is_bot", False)

def format_user_data_as_text(data: dict) -> str:
    output = f"""
✘「 {data['header']} 」
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 BASIC INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
↯ Name: {data['basic_info']['name']}
↯ Full Name: {data['basic_info']['full_name']}
↯ Username: {data['basic_info']['username']}
↯ User ID: {data['basic_info']['user_id']}
↯ Language Code: {data['basic_info']['language_code']}
↯ Phone Number: {data['basic_info']['phone_number']}
↯ Bio: {data['basic_info']['bio']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔰 ACCOUNT STATUS & FLAGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
↯ Is Self: {'Yes' if data['account_status']['is_self'] else 'No'}
↯ Is Bot: {'Yes' if data['account_status']['is_bot'] else 'No'}
↯ Is Contact: {'Yes' if data['account_status']['is_contact'] else 'No'}
↯ Is Mutual Contact: {'Yes' if data['account_status']['is_mutual_contact'] else 'No'}
↯ Is Deleted: {'Yes' if data['account_status']['is_deleted'] else 'No'}
↯ Is Frozen: {'Yes' if data['account_status']['is_frozen'] else 'No'}
↯ Frozen Icon: {data['account_status']['frozen_icon']}
↯ Is Premium: {'Yes' if data['account_status']['is_premium'] else 'No'}
↯ Is Verified: {'Yes' if data['account_status']['is_verified'] else 'No'}
↯ Is Support: {'Yes' if data['account_status']['is_support'] else 'No'}
↯ Is Scam: {'Yes' if data['account_status']['is_scam'] else 'No'}
↯ Is Fake: {'Yes' if data['account_status']['is_fake'] else 'No'}
↯ Is Restricted: {'Yes' if data['account_status']['is_restricted'] else 'No'}
↯ Is Contacts Only: {'Yes' if data['account_status']['is_contacts_only'] else 'No'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 BOT-SPECIFIC INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
↯ Is Bot Business: {'Yes' if data['bot_info']['is_bot_business'] else 'No'}
↯ Active Users: {data['bot_info']['active_users']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 NETWORK & STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
↯ Data Center: {data['network_status']['data_center']}
↯ Status: {data['network_status']['status']}
↯ Last Online: {data['network_status']['last_online']}
↯ Next Offline: {data['network_status']['next_offline']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎨 CUSTOMIZATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
↯ Emoji Status: {data['customization']['emoji_status']}
↯ Reply Color: {data['customization']['reply_color']}
↯ Profile Color: {data['customization']['profile_color']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📸 PROFILE PICTURE URL (via tmpfiles.org)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
↯ Profile Picture: {data['profile_picture']['url']}
"""

    if 'all_usernames' in data:
        usernames_list = ', '.join(data['all_usernames'])
        output += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        output += f"🔗 ALL USERNAMES\n"
        output += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        output += f"↯ {usernames_list}\n"

    if 'restrictions' in data:
        output += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        output += f"⚠️ RESTRICTIONS\n"
        output += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for restriction in data['restrictions']:
            output += f"↯ {restriction}\n"

    return output

def format_group_data_as_text(data: dict) -> str:
    entity_label = "Group Information" if data['type'] == 'group' else "Channel Information"
    return f"""
✘「 {entity_label} ↯ 」
↯ Title: {data['title']}
↯ Username: {data['username']}
↯ Chat ID: {data['chat_id']}
↯ Type: {data['entity_type']}
↯ Members Count: {data['members_count']}

↯ Verified: {'Yes' if data['verified'] else 'No'}
↯ Scam: {'Yes' if data['scam'] else 'No'}
↯ Fake: {'Yes' if data['fake'] else 'No'}
↯ Safety Status: {data['safety_status']}

↯ Description: {data['description']}
↯ Profile Picture URL (via tmpfiles.org): {data['profile_picture']['url']}
"""


async def download_raw_video_profile(photo, filepath: str) -> Optional[str]:
    try:
        if not hasattr(photo, 'video_sizes') or not photo.video_sizes:
            return None

        video_size = photo.video_sizes[0]

        location = types.InputPhotoFileLocation(
            id=photo.id,
            access_hash=photo.access_hash,
            file_reference=photo.file_reference,
            thumb_size=video_size.type
        )

        file_data = b""
        offset = 0
        limit = 524288

        while True:
            chunk = await bot.invoke(
                functions.upload.GetFile(
                    location=location,
                    offset=offset,
                    limit=limit,
                    precise=True,
                    cdn_supported=True
                )
            )

            if not chunk.bytes:
                break

            file_data += chunk.bytes
            offset += len(chunk.bytes)

            if len(file_data) >= getattr(video_size, 'size', 0):
                break

        with open(filepath, "wb") as f:
            f.write(file_data)

        return filepath
    except Exception as e:
        print(f"Error in download_raw_video_profile: {e}")
        return None

async def get_profile_picture_url(entity: Union[User, Chat], entity_id: int, request: Request) -> tuple[str, Optional[str]]:
    try:
        if not hasattr(entity, 'photo') or not entity.photo:
            return ("No Profile Picture", None)

        has_video = getattr(entity.photo, 'has_video', False)

        try:
            peer = await bot.resolve_peer(entity_id)
            result = await bot.invoke(
                functions.photos.GetUserPhotos(
                    user_id=peer,
                    offset=0,
                    max_id=0,
                    limit=1
                )
            )

            if result.photos:
                photo = result.photos[0]
                video_sizes = getattr(photo, 'video_sizes', None)

                if video_sizes and len(video_sizes) > 0:
                    video_size = video_sizes[0]
                    v_type = str(getattr(video_size, 'type', '')).lower()
                    ext = "webm" if v_type == 'u' or "webm" in v_type else "mp4"
                    filename = f"profile_{entity_id}_animated.{ext}"
                    filepath = f"{TEMP_IMAGES_DIR}/{filename}"

                    downloaded_path = await download_raw_video_profile(photo, filepath)

                    if downloaded_path and os.path.exists(downloaded_path):
                        asyncio.create_task(delete_image_after_delay(downloaded_path, 45))
                        return (str(request.url_for('temp_images', path=os.path.basename(downloaded_path))), downloaded_path)
        except Exception as e:
            print(f"GetUserPhotos exception: {e}")

        if hasattr(entity.photo, 'big_file_id') and entity.photo.big_file_id:
            try:
                big_file_id = entity.photo.big_file_id
                ext = "mp4" if has_video else "jpg"
                filename = f"profile_{entity_id}_animated.{ext}" if has_video else f"profile_{entity_id}_640.jpg"
                filepath = f"{TEMP_IMAGES_DIR}/{filename}"

                downloaded_path = await bot.download_media(big_file_id, file_name=filepath)

                if downloaded_path and os.path.exists(downloaded_path):
                    asyncio.create_task(delete_image_after_delay(downloaded_path, 45))
                    return (str(request.url_for('temp_images', path=os.path.basename(downloaded_path))), downloaded_path)
            except Exception as e:
                print(f"download_media big_file_id exception: {e}")


        username = getattr(entity, 'username', None)
        if username:
            return (f"https://t.me/i/userpic/320/{username}.jpg", None)

        return ("Has Profile Picture (direct URL unavailable)", None)

    except Exception as e:
        if hasattr(entity, 'photo') and entity.photo:
            username = getattr(entity, 'username', None)
            if username:
                return (f"https://t.me/i/userpic/320/{username}.jpg", None)
            else:
                return ("Has Profile Picture (no public username)", None)
        return ("No Profile Picture", None)




# ─────────────────────────────────────────────
# 🔎 /get_user_info ENDPOINT
# ─────────────────────────────────────────────

@app.get("/get_user_info")
async def get_user_info(
    request: Request,
    identifier: Optional[str] = Query(
        default=None,
        description="Username (without @) **or** numeric user-id",
    ),
    username: Optional[str] = Query(
        default=None,
        description="[DEPRECATED] Use ?identifier= instead. Present for backward-compatibility.",
    ),
    format: Optional[str] = Query(
        default="json",
        description="Response format: 'json' or 'text'",
    ),
):
    if identifier is None and username is None:
        raise HTTPException(
            status_code=400,
            detail="Please supply ?identifier=<username|user_id> or ?username=<username|user_id>",
        )

    await ensure_bot_started()

    key = (identifier or username or "").lstrip("@")
    target: Union[int, str] = int(key) if key.isdigit() else key

    obj: Union[User, Chat, ChatPreview]
    entity_type: str

    try:
        user_result = await bot.get_users(target)
        if isinstance(user_result, list):
            if len(user_result) == 0:
                raise ValueError("No user found")
            obj = user_result[0]
        else:
            obj = user_result

        if not isinstance(obj, User):
            raise ValueError("Expected User object")

        entity_type = "user"
    except PeerIdInvalid:
        raise HTTPException(
            status_code=403,
            detail=(
                "Bot has no access to this user. The user must start the bot or share a "
                "common group/channel with the bot before their profile can be fetched."
            ),
        )
    except FloodWait as e:
        raise HTTPException(
            status_code=429,
            detail=f"Telegram API Limit (FloodWait): Telegram requested a wait of {e.value} seconds."
        )
    except Exception:
        try:
            chat_result = await bot.get_chat(target)
            obj = chat_result

            if isinstance(obj, Chat):
                chat_type_enum = getattr(obj, 'type', None)
                if chat_type_enum:
                    entity_type = str(chat_type_enum).split('.')[-1].lower()
                else:
                    entity_type = "chat"
            else:
                entity_type = "chat"
        except PeerIdInvalid:
            raise HTTPException(
                status_code=403,
                detail="Bot has no access to this entity."
            )
        except FloodWait as e:
            raise HTTPException(
                status_code=429,
                detail=f"Telegram API Limit (FloodWait): Telegram requested a wait of {e.value} seconds."
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error: {e}")


    if entity_type == "user":
        if not isinstance(obj, User):
            raise HTTPException(status_code=500, detail="Unexpected type error")

        user: User = obj

        # Get user bio information
        user_bio = await get_user_bio(target)

        dc_id_value = getattr(user, "dc_id", None)
        dc_location = DC_LOCATIONS.get(dc_id_value, "Unknown") if dc_id_value is not None else "Unknown"

        status = "Unknown"
        last_online_str = "N/A"

        if hasattr(user, 'status') and user.status:
            status_str = str(user.status).upper()
            if "ONLINE" in status_str and "RECENTLY" not in status_str:
                status = "Online"
                last_online_str = "Currently Online"
            elif "OFFLINE" in status_str:
                status = "Offline"
                if hasattr(user, 'last_online_date') and user.last_online_date:
                    last_online_str = user.last_online_date.strftime('%Y-%m-%d %H:%M:%S UTC')
                else:
                    last_online_str = "Offline"
            elif "RECENTLY" in status_str:
                status = "Recently online"
                last_online_str = "Recently"
            elif "WEEK" in status_str:
                status = "Within a week"
                last_online_str = "Last seen within a week"
            elif "MONTH" in status_str:
                status = "Within a month"
                last_online_str = "Last seen within a month"
            elif "LONG_AGO" in status_str:
                status = "Long ago"
                last_online_str = "Last seen long ago"

        full_profile_pic_url, local_file_path = await get_profile_picture_url(user, user.id, request)

        username_clean = user.username if hasattr(user, 'username') and user.username else None
        public_tg_userpic = f"https://t.me/i/userpic/320/{username_clean}.jpg" if username_clean else None

        tmpfiles_url = "No Profile Picture"

        if local_file_path:
            uploaded = await upload_to_tmpfiles(local_file_path)
            if uploaded and uploaded.startswith("http") and "failed" not in uploaded.lower():
                tmpfiles_url = uploaded
            elif full_profile_pic_url and ("http://" in full_profile_pic_url or "https://" in full_profile_pic_url or full_profile_pic_url.startswith("/")):
                tmpfiles_url = full_profile_pic_url
            elif public_tg_userpic:
                tmpfiles_url = public_tg_userpic
        elif full_profile_pic_url and ("http://" in full_profile_pic_url or "https://" in full_profile_pic_url or full_profile_pic_url.startswith("/")):
            tmpfiles_url = full_profile_pic_url
        elif public_tg_userpic:
            tmpfiles_url = public_tg_userpic


        header = "Bot Info" if is_real_bot(user) else "User Info"

        if hasattr(user, 'username') and user.username:
            username_display = f"@{user.username}"
        else:
            username_display = "No Username"

        data = {
            "type": "user",
            "header": "User Info",
            "basic_info": {
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                "full_name": getattr(user, 'full_name', 'N/A'),
                "username": username_display,
                "user_id": user.id,
                "language_code": getattr(user, 'language_code', 'N/A'),
                "phone_number": getattr(user, 'phone_number', 'Hidden/N/A'),
                "bio": user_bio  # Added bio information
            },
            "account_status": {
                "is_self": getattr(user, 'is_self', False),
                "is_bot": getattr(user, 'is_bot', False),
                "is_contact": getattr(user, 'is_contact', False),
                "is_mutual_contact": getattr(user, 'is_mutual_contact', False),
                "is_deleted": getattr(user, 'is_deleted', False),
                "is_frozen": getattr(user, 'is_frozen', False),
                "frozen_icon": getattr(user, 'frozen_icon', 'N/A'),
                "is_premium": getattr(user, 'is_premium', False),
                "is_verified": getattr(user, 'is_verified', False),
                "is_support": getattr(user, 'is_support', False),
                "is_scam": getattr(user, 'is_scam', False),
                "is_fake": getattr(user, 'is_fake', False),
                "is_restricted": getattr(user, 'is_restricted', False),
                "is_contacts_only": getattr(user, 'is_contacts_only', False)
            },
            "bot_info": {
                "is_bot_business": getattr(user, 'is_bot_business', False),
                "active_users": getattr(user, 'active_users', 'N/A')
            },
            "network_status": {
                "data_center": dc_location,
                "status": status,
                "last_online": last_online_str,
                "next_offline": user.next_offline_date.strftime('%Y-%m-%d %H:%M:%S UTC') if hasattr(user, 'next_offline_date') and user.next_offline_date else 'N/A'
            },
            "customization": {
                "emoji_status": str(getattr(user, 'emoji_status', 'N/A')),
                "reply_color": str(getattr(user, 'reply_color', 'N/A')),
                "profile_color": str(getattr(user, 'profile_color', 'N/A'))
            },
            "profile_picture": {
                "url": tmpfiles_url
            }
        }

        usernames_attr = getattr(user, 'usernames', None)
        if usernames_attr:
            data["all_usernames"] = [f"@{u.username}" for u in usernames_attr if hasattr(u, 'username')]

        if hasattr(user, 'restrictions') and user.restrictions:
            data["restrictions"] = [str(r) for r in user.restrictions]

        if format == "text":
            return PlainTextResponse(content=format_user_data_as_text(data))
        return JSONResponse(content=data)

    elif entity_type in {"group", "supergroup"}:
        if not isinstance(obj, Chat):
            raise HTTPException(status_code=500, detail="Unexpected type error")

        chat: Chat = obj
        try:
            members_count = await bot.get_chat_members_count(chat.id)
        except Exception:
            members_count = "Unknown"

        full_profile_pic_url, local_file_path = await get_profile_picture_url(chat, chat.id, request)

        tmpfiles_url = "No Profile Picture"
        if local_file_path:
            tmpfiles_url = await upload_to_tmpfiles(local_file_path)
        elif full_profile_pic_url and full_profile_pic_url not in ["No Profile Picture", "Has Profile Picture (direct URL unavailable)", "Has Profile Picture (no public username)"]:
            tmpfiles_url = full_profile_pic_url

        fake_status = "Yes" if getattr(chat, "is_fake", False) else "No"
        safety_status = "Unsafe" if getattr(chat, "is_scam", False) else "Safe"

        data = {
            "type": "group",
            "title": chat.title,
            "username": f"@{chat.username}" if chat.username else "N/A",
            "chat_id": chat.id,
            "entity_type": entity_type.capitalize(),
            "members_count": str(members_count),
            "verified": getattr(chat, 'is_verified', False),
            "scam": getattr(chat, 'is_scam', False),
            "fake": getattr(chat, "is_fake", False),
            "safety_status": safety_status,
            "description": chat.description or 'No description',
            "profile_picture": {
                "url": tmpfiles_url
            }
        }

        if format == "text":
            return PlainTextResponse(content=format_group_data_as_text(data))
        return JSONResponse(content=data)

    elif entity_type == "channel":
        if not isinstance(obj, Chat):
            raise HTTPException(status_code=500, detail="Unexpected type error")

        channel: Chat = obj
        try:
            members_count = await bot.get_chat_members_count(channel.id)
        except Exception:
            members_count = "Unknown"

        full_profile_pic_url, local_file_path = await get_profile_picture_url(channel, channel.id, request)

        tmpfiles_url = "No Profile Picture"
        if local_file_path:
            tmpfiles_url = await upload_to_tmpfiles(local_file_path)
        elif full_profile_pic_url and full_profile_pic_url not in ["No Profile Picture", "Has Profile Picture (direct URL unavailable)", "Has Profile Picture (no public username)"]:
            tmpfiles_url = full_profile_pic_url

        fake_status = "Yes" if getattr(channel, "is_fake", False) else "No"
        safety_status = "Unsafe" if getattr(channel, "is_scam", False) else "Safe"

        data = {
            "type": "channel",
            "title": channel.title,
            "username": f"@{channel.username}" if channel.username else "N/A",
            "chat_id": channel.id,
            "entity_type": "Channel",
            "members_count": str(members_count),
            "verified": getattr(channel, 'is_verified', False),
            "scam": getattr(channel, 'is_scam', False),
            "fake": getattr(channel, "is_fake", False),
            "safety_status": safety_status,
            "description": channel.description or 'No description',
            "profile_picture": {
                "url": tmpfiles_url
            }
        }

        if format == "text":
            return PlainTextResponse(content=format_group_data_as_text(data))
        return JSONResponse(content=data)

    return JSONResponse(content={"error": "Unknown entity."})


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
