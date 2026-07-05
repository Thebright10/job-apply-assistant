"""
Your profile — pulled from https://thebright10.github.io/Portfolio_Sudip/
Edit freely; every field here gets used to personalize application drafts.
"""

PROFILE = {
    "name": "Sudip Kumar Adak",
    "email": "adaksudip956@gmail.com",
    "phone": "",  # add if you want it in the signature
    "location": "Pune, Maharashtra, India",
    "linkedin": "https://www.linkedin.com/in/sudip-kumar-adak-26b303245/",
    "github": "https://github.com/Thebright10",
    "portfolio": "https://thebright10.github.io/Portfolio_Sudip/",
    "education": "MCA (in progress), Pimpri Chinchwad University; BCA, Techno India Institute of Technology",
    "roles_seeking": ["Software Developer", "Backend Developer", "Frontend Developer",
                      "Data Analyst", "Python Developer", "Django Developer", "IT / Support"],
    "skills": ["Python", "Django", "SQL", "Machine Learning", "Data Visualization",
               "Java", "C", "Web Development", "HTML/CSS", "JavaScript", "NLP"],
    "flagship_project": {
        "name": "MindFlow — AI Mental Health Companion",
        "desc": "an AI-powered mental health platform with real-time emotion detection via NLP, "
                "an empathetic chatbot, wellness tracking, and crisis-support resources, built on Django + ML",
        "link": "https://mental-health-ai-xy7u.onrender.com",
    },
    "other_projects": [
        "an e-commerce platform with cart, auth, and responsive UI (JS/HTML/CSS)",
        "a Python data-analytics dashboard with dynamic charts and KPI reporting",
        "Grilli, a restaurant table-booking site with a login portal and reservation system",
    ],
    "resume_path": "",  # optional: local path to resume.pdf to attach to email drafts
}

# Keywords used to match/filter job listings. Keep broad but relevant — too narrow = few matches.
SEARCH_KEYWORDS = [
    "python developer", "django developer", "backend developer", "software developer fresher",
    "web developer", "data analyst", "machine learning intern", "full stack developer intern",
    "frontend developer", "python intern",
]

# Job title words that auto-disqualify a listing (adjust as you like)
EXCLUDE_KEYWORDS = ["senior", "10+ years", "staff engineer", "principal", "lead engineer"]
