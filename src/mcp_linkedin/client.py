from linkedin_api import Linkedin
from fastmcp import FastMCP
import os
import logging
import json
import uuid

mcp = FastMCP("mcp-linkedin")
logger = logging.getLogger(__name__)

def get_client():
    return Linkedin(os.getenv("LINKEDIN_EMAIL"), os.getenv("LINKEDIN_PASSWORD"), debug=True)

@mcp.tool()
def get_feed_posts(limit: int = 10, offset: int = 0) -> str:
    """
    Retrieve LinkedIn feed posts.
    :return: List of feed post details as JSON string
    """
    client = get_client()
    try:
        post_urns = client.get_feed_posts(limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"Error: {e}")
        return json.dumps({"error": str(e)})

    posts = []
    for urn in post_urns:
        posts.append({
            "author": urn.get("author_name", "Unknown"),
            "content": urn.get("content", "")
        })

    return json.dumps({"posts": posts}, ensure_ascii=False)

@mcp.tool()
def search_jobs(keywords: str, limit: int = 3, offset: int = 0, location: str = '') -> str:
    """
    Search for jobs on LinkedIn.
    :param keywords: Job search keywords
    :param limit: Maximum number of job results
    :param location: Optional location filter
    :return: List of job details as JSON string
    """
    client = get_client()
    try:
        jobs = client.search_jobs(
            keywords=keywords,
            location_name=location,
            limit=limit,
            offset=offset,
        )
        job_list = []
        for job in jobs:
            try:
                job_id = job["entityUrn"].split(":")[-1]
                job_data = client.get_job(job_id=job_id)
                company_details = job_data.get("companyDetails", {})
                company_key = "com.linkedin.voyager.deco.jobs.web.shared.WebCompactJobPostingCompany"
                company_name = (
                    company_details
                    .get(company_key, {})
                    .get("companyResolutionResult", {})
                    .get("name", "Unknown Company")
                )
                job_list.append({
                    "title": job_data.get("title", "Unknown Title"),
                    "company": company_name,
                    "location": job_data.get("formattedLocation", "Unknown Location"),
                    "description": job_data.get("description", {}).get("text", "")[:500]
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
    :param recipient_profile_url: LinkedIn profile URL or public identifier e.g. 'johndoe' or 'https://www.linkedin.com/in/johndoe'
    :param message: The message text to send
    :return: Success or error as JSON string
    """
    client = get_client()
    try:
        profile_id = recipient_profile_url.strip("/").split("/")[-1]

        # Step 1: get profile
        profile = client.get_profile(public_id=profile_id)
        if not profile:
            return json.dumps({"error": f"Could not find profile for '{profile_id}'"})

        # Step 2: get raw numeric/alphanumeric profile_id from profile
        raw_profile_id = profile.get("profile_id")
        if not raw_profile_id:
            entity_urn = profile.get("entityUrn", "")
            raw_profile_id = entity_urn.split(":")[-1]
        if not raw_profile_id:
            return json.dumps({"error": f"Could not extract URN id for '{profile_id}'"})

        logger.info(f"Resolved profile_id: {raw_profile_id}")

        # Step 3: get existing conversation urn_id
        conversation = client.get_conversation_details(raw_profile_id)
        if not conversation:
            return json.dumps({"error": "No existing conversation found. You must be 1st-degree connected with this person."})

        conversation_urn_id = conversation.get("entityUrn", "").split(":")[-1]
        if not conversation_urn_id:
            conversation_urn_id = str(conversation.get("id", ""))
        if not conversation_urn_id:
            return json.dumps({"error": "Could not extract conversation URN ID."})

        logger.info(f"Using conversation_urn_id: {conversation_urn_id}")

        # Step 4: send message using conversation_urn_id (most reliable path)
        err = client.send_message(
            conversation_urn_id=conversation_urn_id,
            message_body=message
        )

        if err:
            return json.dumps({"error": "Message send failed. LinkedIn returned an error."})
        return json.dumps({"success": True, "message": f"Message sent to {profile_id}!"})

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
        profile = client.get_profile(public_id=None)
        if not profile:
            return json.dumps({"error": "Could not retrieve your profile."})

        person_urn = profile.get("entityUrn", "")
        if not person_urn:
            return json.dumps({"error": "Could not get your profile URN."})

        client.create_post(text=text, person_urn=person_urn)
        return json.dumps({"success": True, "message": "Post created successfully!"})
    except Exception as e:
        logger.error(f"Error creating post: {e}")
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    mcp.run()
