from linkedin_api import Linkedin
from fastmcp import FastMCP
import os
import logging

mcp = FastMCP("mcp-linkedin")
logger = logging.getLogger(__name__)

def get_client():
    return Linkedin(os.getenv("LINKEDIN_EMAIL"), os.getenv("LINKEDIN_PASSWORD"), debug=True)

@mcp.tool()
def get_feed_posts(limit: int = 10, offset: int = 0) -> str:
    """
    Retrieve LinkedIn feed posts.

    :return: List of feed post details
    """
    client = get_client()
    try:
        post_urns = client.get_feed_posts(limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"Error: {e}")
        return f"Error: {e}"
    
    posts = ""
    for urn in post_urns:
        posts += f"Post by {urn['author_name']}: {urn['content']}\n"

    return posts

@mcp.tool()
def search_jobs(keywords: str, limit: int = 3, offset: int = 0, location: str = '') -> str:
    """
    Search for jobs on LinkedIn.
    
    :param keywords: Job search keywords
    :param limit: Maximum number of job results
    :param location: Optional location filter
    :return: List of job details
    """
    client = get_client()
    jobs = client.search_jobs(
        keywords=keywords,
        location_name=location,
        limit=limit,
        offset=offset,
    )
    job_results = ""
    for job in jobs:
        job_id = job["entityUrn"].split(":")[-1]
        job_data = client.get_job(job_id=job_id)

        job_title = job_data["title"]
        company_name = job_data["companyDetails"]["com.linkedin.voyager.deco.jobs.web.shared.WebCompactJobPostingCompany"]["companyResolutionResult"]["name"]
        job_description = job_data["description"]["text"]
        job_location = job_data["formattedLocation"]

        job_results += f"Job by {job_title} at {company_name} in {job_location}: {job_description}\n\n"

    return job_results

@mcp.tool()
def send_message(recipient_profile_url: str, message: str) -> str:
    """
    Send a direct message to a LinkedIn connection.

    :param recipient_profile_url: The LinkedIn profile URL or public identifier of the recipient
                                   e.g. 'https://www.linkedin.com/in/johndoe' or just 'johndoe'
    :param message: The message text to send
    :return: Success or error message
    """
    client = get_client()
    try:
        # Extract public identifier from URL if full URL is provided
        profile_id = recipient_profile_url.strip("/").split("/")[-1]
        
        # Get the recipient's profile to obtain their URN
        profile = client.get_profile(public_id=profile_id)
        if not profile:
            return f"Error: Could not find profile for '{profile_id}'"
        
        profile_urn = profile.get("entityUrn", "").replace("urn:li:fs_profile:", "")
        if not profile_urn:
            return f"Error: Could not get URN for profile '{profile_id}'"

        # Send the message
        client.send_message(message_body=message, recipients=[profile_urn])
        return f"Message successfully sent to {profile_id}!"
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return f"Error sending message: {e}"

@mcp.tool()
def create_post(text: str) -> str:
    """
    Create a new LinkedIn post on your profile.

    :param text: The text content of the post
    :return: Success or error message
    """
    client = get_client()
    try:
        # Get own profile URN
        profile = client.get_profile(public_id=None)
        if not profile:
            return "Error: Could not retrieve your profile."
        
        person_urn = profile.get("entityUrn", "")
        if not person_urn:
            return "Error: Could not get your profile URN."

        # Create the post using the LinkedIn API
        client.create_post(text=text, person_urn=person_urn)
        return f"Post created successfully!"
    except Exception as e:
        logger.error(f"Error creating post: {e}")
        return f"Error creating post: {e}"

if __name__ == "__main__":
    print(search_jobs(keywords="data engineer", location="Jakarta", limit=2))
