from linkedin_api import Linkedin
from fastmcp import FastMCP
import os
import logging
import json

mcp = FastMCP("mcp-linkedin")
logger = logging.getLogger(__name__)

def get_client():
    """
    Authenticate using cookies (preferred) to bypass 2FA/CAPTCHA.
    Falls back to email/password if cookies not set.
    Set LINKEDIN_COOKIES env var as JSON: '{"li_at": "...", "JSESSIONID": "..."}'
    """
    email = os.getenv("LINKEDIN_EMAIL", "")
    password = os.getenv("LINKEDIN_PASSWORD", "")
    cookies_str = os.getenv("LINKEDIN_COOKIES")

    if cookies_str:
        try:
            cookies = json.loads(cookies_str)
            return Linkedin(email, "", cookies=cookies)
        except Exception as e:
            logger.warning(f"Failed to parse LINKEDIN_COOKIES: {e}, falling back to password auth")

    return Linkedin(email, password)

@mcp.tool()
def get_feed_posts(limit: int = 5) -> str:
    """
    Retrieve LinkedIn feed posts.
    :param limit: Number of posts to fetch (default 5 to avoid timeout)
    :return: List of feed post details as JSON string
    """
    client = get_client()
    try:
        posts_raw = client.get_feed_posts(limit=limit)
    except Exception as e:
        logger.error(f"Error: {e}")
        return json.dumps({"error": str(e)})

    posts = []
    for p in posts_raw:
        posts.append({
            "author": p.get("author_name", "Unknown"),
            "content": p.get("content", "")[:300]
        })

    return json.dumps({"posts": posts}, ensure_ascii=False)

@mcp.tool()
def search_jobs(keywords: str, limit: int = 3, location: str = '') -> str:
    """
    Search for jobs on LinkedIn. Returns basic info only to avoid timeouts.
    :param keywords: Job search keywords
    :param limit: Max results (keep low to avoid timeout)
    :param location: Optional location filter
    :return: List of job details as JSON string
    """
    client = get_client()
    try:
        jobs = client.search_jobs(
            keywords=keywords,
            location_name=location,
            limit=limit,
        )
        job_list = []
        for job in jobs:
            try:
                title = job.get("title", "Unknown Title")
                entity_urn = job.get("entityUrn", "")
                company = job.get("companyName", "Unknown Company")
                location_str = job.get("formattedLocation", "Unknown Location")
                job_list.append({
                    "title": title,
                    "company": company,
                    "location": location_str,
                    "urn": entity_urn,
                })
            except Exception as e:
                logger.error(f"Error parsing job: {e}")
                continue

        return json.dumps({"jobs": job_list}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error searching jobs: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
def send_message(recipient_profile_url: str, message: str) -> str:
    """
    Send a direct message to a LinkedIn connection.
    :param recipient_profile_url: Profile URL or slug e.g. 'johndoe' or 'https://www.linkedin.com/in/johndoe'
    :param message: The message text to send
    :return: Success or error as JSON string
    """
    client = get_client()
    try:
        # Extract slug from URL if needed
        profile_id = recipient_profile_url.strip("/").split("/")[-1]

        # Get profile to resolve numeric profile_id
        profile = client.get_profile(public_id=profile_id)
        if not profile:
            return json.dumps({"error": f"Could not find profile for '{profile_id}'"})

        # Get numeric profile_id (what the library expects for recipients)
        raw_profile_id = profile.get("profile_id")
        if not raw_profile_id:
            raw_profile_id = profile.get("entityUrn", "").split(":")[-1]
        if not raw_profile_id:
            return json.dumps({"error": f"Could not extract profile URN for '{profile_id}'"})

        logger.info(f"Sending message to raw_profile_id: {raw_profile_id}")

        # Try via existing conversation first
        try:
            conversation = client.get_conversation_details(raw_profile_id)
            if conversation:
                conv_id = conversation.get("id") or conversation.get("entityUrn", "").split(":")[-1]
                if conv_id:
                    err = client.send_message(conversation_urn_id=str(conv_id), message_body=message)
                    if not err:
                        return json.dumps({"success": True, "message": f"Message sent to {profile_id} via existing conversation!"})
        except Exception as conv_err:
            logger.warning(f"Conversation lookup failed: {conv_err}, trying recipients method")

        # Fallback: send via recipients list
        err = client.send_message(recipients=[raw_profile_id], message_body=message)
        if not err:
            return json.dumps({"success": True, "message": f"Message sent to {profile_id}!"})
        return json.dumps({"error": "Send failed. Ensure you are 1st-degree connected with this person."})

    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
def create_post(text: str) -> str:
    """
    Create a new post on your LinkedIn profile.
    :param text: The text content of the post
    :return: Success or error as JSON string
    """
    client = get_client()
    try:
        # get_user_profile() is more reliable for own profile
        me = client.get_user_profile()
        if not me:
            return json.dumps({"error": "Could not retrieve your profile."})

        # Extract full URN e.g. urn:li:person:ABC123
        urn = me.get("entityUrn", "")
        if not urn:
            plain_id = me.get("plainId") or me.get("miniProfile", {}).get("entityUrn", "").split(":")[-1]
            urn = f"urn:li:person:{plain_id}"
        if not urn:
            return json.dumps({"error": "Could not resolve your URN."})

        # Use client.post() — correct method name in linkedin_api
        client.post(urn=urn, text=text)
        return json.dumps({"success": True, "message": "Post created successfully!"})

    except AttributeError:
        # Some versions use create_post instead
        try:
            profile = client.get_profile(public_id=None)
            person_urn = profile.get("entityUrn", "")
            client.create_post(text=text, person_urn=person_urn)
            return json.dumps({"success": True, "message": "Post created successfully!"})
        except Exception as e2:
            return json.dumps({"error": f"create_post also failed: {str(e2)}"})
    except Exception as e:
        logger.error(f"Error creating post: {e}")
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    mcp.run()
