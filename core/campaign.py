"""
Learn With Communities Campaign - Official Badge Specification & Evaluator
"""
from typing import List, Dict, Any
import re

# The 10 official skill badges required for completion of the Learn With Communities Campaign
CAMPAIGN_BADGES = [
    {
        "id": "genai-agent-platform",
        "title": "Explore Generative AI in Agent Platform",
        "category": "Generative AI",
        "description": "Learn fundamentals of generative AI agents and workflows on Google Cloud.",
        "icon": "bot"
    },
    {
        "id": "store-manage-data",
        "title": "Store, Process, and Manage Data on Google Cloud - Console",
        "category": "Cloud Infrastructure & Data",
        "description": "Configure storage buckets, Cloud SQL, and basic data lifecycle management.",
        "icon": "database"
    },
    {
        "id": "speech-api",
        "title": "Using the Google Cloud Speech API",
        "category": "AI & Machine Learning",
        "description": "Convert audio to text and leverage speech recognition models.",
        "icon": "mic"
    },
    {
        "id": "gemini-enterprise-app",
        "title": "Create Your First Gemini Enterprise Application",
        "category": "Generative AI",
        "description": "Build an enterprise application powered by Google Gemini models.",
        "icon": "sparkles"
    },
    {
        "id": "build-website-cloud",
        "title": "Build a Website on Google Cloud",
        "category": "Web & Cloud Run",
        "description": "Deploy web architectures using compute and container services on GCP.",
        "icon": "globe"
    },
    {
        "id": "vision-api",
        "title": "Analyze Images with the Cloud Vision API",
        "category": "AI & Machine Learning",
        "description": "Extract features, detect labels, and process images using Cloud Vision.",
        "icon": "camera"
    },
    {
        "id": "ai-studio-prototypes",
        "title": "Develop AI-Powered Prototypes in Google AI Studio",
        "category": "Generative AI",
        "description": "Prototype and prompt-tune Gemini models quickly using Google AI Studio.",
        "icon": "cpu"
    },
    {
        "id": "speech-language-solutions",
        "title": "Implement Speech and Language Solutions with Pre-trained APIs",
        "category": "AI & Machine Learning",
        "description": "Combine Speech-to-Text, Natural Language, and Translation APIs.",
        "icon": "message-square"
    },
    {
        "id": "iam-service-accounts",
        "title": "Configure Service Accounts and IAM Roles for Google Cloud",
        "category": "Security & IAM",
        "description": "Master least-privilege security, IAM roles, and service account keys.",
        "icon": "shield-check"
    },
    {
        "id": "basics-compute",
        "title": "The Basics of Google Cloud Compute",
        "category": "Compute",
        "description": "Provision and manage virtual machines with Compute Engine.",
        "icon": "server"
    }
]

CAMPAIGN_BADGE_TITLES = [b["title"] for b in CAMPAIGN_BADGES]
TOTAL_REQUIRED_BADGES = len(CAMPAIGN_BADGES)


def _normalize(text: str) -> str:
    """Normalize text for resilient string matching."""
    text = re.sub(r'[^\w\s]', '', text.lower())
    return ' '.join(text.split())


def evaluate_candidate(candidate_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates candidate badges against the 10 Learn With Communities Campaign badges.
    Returns structured results including status, completion rate, badge breakdown, and missing badges.
    """
    if candidate_data.get("is_error"):
        return {
            **candidate_data,
            "status": "ERROR",
            "status_label": "Scrape Error",
            "campaign_completed": 0,
            "campaign_total": TOTAL_REQUIRED_BADGES,
            "completion_percentage": 0.0,
            "is_completed": False,
            "earned_campaign_badges": [],
            "missing_campaign_badges": CAMPAIGN_BADGES,
            "other_badges": []
        }

    if candidate_data.get("is_private"):
        return {
            **candidate_data,
            "status": "PRIVATE_PROFILE",
            "status_label": "Private Profile",
            "campaign_completed": 0,
            "campaign_total": TOTAL_REQUIRED_BADGES,
            "completion_percentage": 0.0,
            "is_completed": False,
            "earned_campaign_badges": [],
            "missing_campaign_badges": CAMPAIGN_BADGES,
            "other_badges": []
        }

    user_badges = candidate_data.get("badges", [])
    user_badges_map = {}
    for b in user_badges:
        norm = _normalize(b.get("title", ""))
        user_badges_map[norm] = b

    earned_campaign = []
    missing_campaign = []

    for req in CAMPAIGN_BADGES:
        norm_req = _normalize(req["title"])
        if norm_req in user_badges_map:
            matched_b = user_badges_map[norm_req]
            earned_campaign.append({
                **req,
                "earned": True,
                "earned_date": matched_b.get("date", ""),
                "badge_image": matched_b.get("image", ""),
                "badge_url": matched_b.get("url", "")
            })
        else:
            missing_campaign.append({
                **req,
                "earned": False,
                "earned_date": None,
                "badge_image": "",
                "badge_url": ""
            })

    # Other badges outside the 10 campaign badges (if any)
    norm_campaign_titles = {_normalize(b["title"]) for b in CAMPAIGN_BADGES}
    other_badges = [b for b in user_badges if _normalize(b.get("title", "")) not in norm_campaign_titles]

    completed_count = len(earned_campaign)
    pct = round((completed_count / TOTAL_REQUIRED_BADGES) * 100, 1)

    if completed_count == TOTAL_REQUIRED_BADGES:
        status = "COMPLETED"
        status_label = "Completed (10/10)"
    elif completed_count > 0:
        status = "IN_PROGRESS"
        status_label = f"In Progress ({completed_count}/10)"
    else:
        status = "NOT_STARTED"
        status_label = "Not Started (0/10)"

    return {
        **candidate_data,
        "status": status,
        "status_label": status_label,
        "campaign_completed": completed_count,
        "campaign_total": TOTAL_REQUIRED_BADGES,
        "completion_percentage": pct,
        "is_completed": (completed_count >= TOTAL_REQUIRED_BADGES),
        "earned_campaign_badges": earned_campaign,
        "missing_campaign_badges": missing_campaign,
        "other_badges": other_badges
    }
