"""Job Description Parser Service."""

import re
import unicodedata
import structlog
from app.schemas.job_match import JobDescription
from app.services.parser.cleaner import clean_text
from app.services.parser.entity_extractor import (
    get_nlp_model,
    get_skill_matcher,
    get_skill_casing_map,
)

logger = structlog.get_logger()

# Define section mapping
SECTION_MAPPING = {
    "required_skills": [
        "required skills", "requirements", "minimum qualifications", "what you need",
        "required experience", "basic qualifications", "skills required", "key requirements",
        "essential requirements", "what you'll need", "key skills"
    ],
    "preferred_skills": [
        "preferred skills", "preferred qualifications", "nice to have", "pluses",
        "plus", "desirable skills", "preferred experience", "bonus", "desired skills",
        "preferred", "optional skills"
    ],
    "general_skills": [
        "skills", "technical skills", "core skills", "technologies", "expertise",
        "core competencies", "skills & tools", "general skills", "tools"
    ],
    "responsibilities": [
        "responsibilities", "what you'll do", "role", "key responsibilities", "duties",
        "job duties", "responsibilities:", "what you will do", "roles & responsibilities",
        "roles and responsibilities"
    ],
    "experience": [
        "experience", "work experience", "experience required", "experience:"
    ],
    "education": [
        "education", "academic background", "academic qualifications", "education:",
        "educational requirements"
    ],
    "certifications": [
        "certifications", "credentials", "certifications:", "licenses & certifications",
        "licenses and certifications"
    ]
}

def split_sections(text: str) -> dict[str, str]:
    """
    Split the job description text into logical sections.
    """
    sections = {
        "intro": "",
        "required_skills": "",
        "preferred_skills": "",
        "general_skills": "",
        "responsibilities": "",
        "experience": "",
        "education": "",
        "certifications": ""
    }
    
    current_section = "intro"
    lines = text.split("\n")
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        # Check if line is a section header
        clean_line = stripped.lower().rstrip(":")
        clean_line = clean_line.lstrip("#").strip()
        
        found_section = None
        for sec_name, headers in SECTION_MAPPING.items():
            if clean_line in headers:
                found_section = sec_name
                break
                
        if found_section:
            current_section = found_section
        else:
            if current_section:
                sections[current_section] += line + "\n"
                
    return {k: v.strip() for k, v in sections.items()}

def extract_job_title(text: str) -> str | None:
    """
    Extract the job title from the text using various strategies.
    """
    lines = [line.strip() for line in text.split("\n")]
    
    # 1. Look for first heading (markdown heading starting with #)
    for line in lines:
        if line.startswith("#"):
            title = line.lstrip("#").strip().strip("#*_ ").strip()
            if title:
                return title
                
    # 2. Look for Position:, Role:, Job Title:
    patterns = [
        r"(?i)\bjob\s+title\s*:\s*(.+)$",
        r"(?i)\bposition\s*:\s*(.+)$",
        r"(?i)\brole\s*:\s*(.+)$"
    ]
    for line in lines:
        for pattern in patterns:
            m = re.search(pattern, line)
            if m:
                title = m.group(1).strip().strip("#*_ ").strip()
                if title:
                    return title
                    
    # 3. Fallback: first non-empty line
    for line in lines:
        if line:
            clean_line = line.lstrip("#*-\t ").strip().strip("#*_ ").strip()
            if clean_line:
                return clean_line
                
    return None

def extract_company(text: str) -> str | None:
    """
    Detect the company name from the text.
    """
    lines = [line.strip() for line in text.split("\n")]
    patterns = [
        r"(?i)\bcompany\s*:\s*(.+)$",
        r"(?i)\bemployer\s*:\s*(.+)$",
        r"(?i)\babout\s+company\s*:\s*(.+)$",
        r"(?i)\bhiring\s+company\s*:\s*(.+)$"
    ]
    for line in lines:
        for pattern in patterns:
            m = re.search(pattern, line)
            if m:
                val = m.group(1).strip().strip("#*_ ").strip()
                if val:
                    return val
    return None

def extract_skills(sections: dict, full_text: str) -> tuple[list[str], list[str]]:
    """
    Extract technical skills and categorize into required and preferred skills.
    """
    def match_in_text(txt: str) -> list[str]:
        if not txt:
            return []
        nlp = get_nlp_model()
        matcher = get_skill_matcher()
        casing_map = get_skill_casing_map()
        
        doc = nlp(txt)
        matches = matcher(doc)
        
        extracted = set()
        for match_id, start, end in matches:
            span = doc[start:end]
            span_lower = span.text.lower()
            if span_lower in casing_map:
                val = casing_map[span_lower]
                if len(val) >= 2:
                    extracted.add(val)
        return list(extracted)

    has_skills_sections = bool(sections.get("required_skills") or sections.get("preferred_skills") or sections.get("general_skills"))
    
    if not has_skills_sections:
        # Fallback: parse full text as required_skills
        skills = match_in_text(full_text)
        req = sorted(list(set(skills)), key=str.lower)
        return req, []

    pref = match_in_text(sections.get("preferred_skills", ""))
    req = match_in_text(sections.get("required_skills", "")) + match_in_text(sections.get("general_skills", ""))
        
    req_set = set(req)
    pref_set = set(pref) - req_set
    
    req_sorted = sorted(list(req_set), key=str.lower)
    pref_sorted = sorted(list(pref_set), key=str.lower)
    
    return req_sorted, pref_sorted

def extract_experience(sections: dict, full_text: str) -> list[str]:
    """
    Extract years of experience or experience requirements.
    """
    exp_text = sections.get("experience", "")
    if not exp_text.strip():
        exp_text = full_text
        
    lines = exp_text.split("\n")
    extracted = []
    
    pattern_years = re.compile(r"(?i)\b(?:\d+(?:\+|-|\s*to\s*\d+)?\s*(?:year|yr)s?|minimum\s+(?:of\s+)?\d+\s*(?:year|yr)s?)\b")
    pattern_required = re.compile(r"(?i)\bexperience\s+required\b")
    pattern_colon = re.compile(r"(?i)\bexperience\s*:\s*(.+)$")
    
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
            
        line_clean = re.sub(r"^[•\-\*\+\s]+", "", line_clean).strip()
        
        match_years = pattern_years.search(line_clean)
        match_req = pattern_required.search(line_clean)
        match_colon = pattern_colon.search(line_clean)
        
        if match_years or match_req or match_colon:
            normalized = re.sub(r"\s+", " ", line_clean).strip()
            if normalized and normalized not in extracted:
                extracted.append(normalized)
                
    return extracted

def extract_education(full_text: str) -> list[str]:
    """
    Detect degrees and education requirements.
    """
    edu_patterns = {
        "Bachelor": [r"\bBachelor(?:'s)?\b"],
        "Master": [r"\bMaster(?:'s)?\b"],
        "B.Tech": [r"\bB\.?\s?Tech\b"],
        "M.Tech": [r"\bM\.?\s?Tech\b"],
        "MBA": [r"\bMBA\b"],
        "BE": [r"\bBE\b"],
        "BS": [r"\bBS\b"],
        "MS": [r"\bMS\b"],
        "PhD": [r"\bPh\.?D\b", r"\bPhD\b"],
        "Diploma": [r"\bDiploma\b"]
    }
    extracted = set()
    for degree_name, patterns in edu_patterns.items():
        for pattern in patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                extracted.add(degree_name)
                break
    return sorted(list(extracted), key=str.lower)

def extract_certifications(full_text: str) -> list[str]:
    """
    Detect certifications from the text.
    """
    certs = [
        "AWS", "Azure", "Oracle", "OCI", "TensorFlow", "Kubernetes",
        "Docker", "Cisco", "Microsoft", "Google Cloud"
    ]
    # Add other common certifications for "etc."
    etc_certs = ["PMP", "CISSP", "GCP", "Scrum Master", "Salesforce"]
    all_certs = certs + etc_certs
    
    extracted = set()
    for cert in all_certs:
        pattern = rf"\b{re.escape(cert)}\b"
        if re.search(pattern, full_text, re.IGNORECASE):
            extracted.add(cert)
            
    return sorted(list(extracted), key=str.lower)

def extract_responsibilities(sections: dict, full_text: str) -> list[str]:
    """
    Extract responsibilities bullet points.
    """
    resp_text = sections.get("responsibilities", "")
    if not resp_text.strip():
        return []
        
    lines = resp_text.split("\n")
    bullets = []
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
            
        cleaned = re.sub(r"^[•\-\*\+\s]+", "", line_clean)
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", cleaned).strip()
        cleaned = cleaned.strip("#*_ ").strip()
        
        if cleaned:
            bullets.append(cleaned)
            
    return bullets

def extract_keywords(
    text: str | None = None,
    skills: list[str] | None = None,
    education: list[str] | None = None,
    certifications: list[str] | None = None,
    experience: list[str] | None = None,
    responsibilities: list[str] | None = None
) -> list[str]:
    """
    Extract keywords and key terminology from the job description text or fields.
    """
    keywords = set()
    
    if skills is not None or education is not None or certifications is not None or experience is not None or responsibilities is not None:
        skills = skills or []
        education = education or []
        certifications = certifications or []
        experience = experience or []
        responsibilities = responsibilities or []
        
        for item in skills + education + certifications:
            clean_item = item.strip().lower()
            if clean_item:
                keywords.add(clean_item)
                
        combined_text = " ".join(experience + responsibilities)
    else:
        combined_text = text or ""
        
    if combined_text.strip():
        try:
            nlp = get_nlp_model()
            doc = nlp(combined_text)
            for token in doc:
                if token.is_alpha and not token.is_stop and len(token.text) >= 3:
                    if token.pos_ in {"NOUN", "PROPN", "ADJ"}:
                        keywords.add(token.text.lower())
        except Exception:
            words = re.findall(r"\b[a-zA-Z]{3,}\b", combined_text)
            stop_words = {"and", "the", "for", "with", "you", "are", "our", "will", "that", "this", "your", "from"}
            for w in words:
                w_lower = w.lower()
                if w_lower not in stop_words:
                    keywords.add(w_lower)
                    
    return sorted(list(keywords))

def normalize_job_description(data: dict) -> dict:
    """
    Normalize extracted job description fields to a standard structure.
    """
    def clean_str(s: str | None) -> str | None:
        if s is None:
            return None
        # Unicode normalization
        normalized = unicodedata.normalize("NFKC", s)
        # Collapse multiple spaces
        collapsed = re.sub(r"\s+", " ", normalized)
        return collapsed.strip()

    def clean_list(lst: list[str] | None, is_keyword: bool = False, use_skill_casing: bool = False) -> list[str]:
        if not lst:
            return []
        cleaned = []
        seen = set()
        casing_map = get_skill_casing_map() if use_skill_casing else {}
        for item in lst:
            if not isinstance(item, str):
                continue
            item_clean = clean_str(item)
            if is_keyword:
                item_clean = item_clean.lower()
            elif use_skill_casing:
                item_clean = casing_map.get(item_clean.lower(), item_clean)
                
            if not item_clean:
                continue
            
            key = item_clean.lower()
            if key not in seen:
                seen.add(key)
                cleaned.append(item_clean)
        return sorted(cleaned, key=str.lower)

    normalized_data = {}
    normalized_data["title"] = clean_str(data.get("title"))
    normalized_data["company"] = clean_str(data.get("company"))
    
    normalized_data["required_skills"] = clean_list(data.get("required_skills"), use_skill_casing=True)
    normalized_data["preferred_skills"] = clean_list(data.get("preferred_skills"), use_skill_casing=True)
    normalized_data["education"] = clean_list(data.get("education"))
    normalized_data["experience"] = clean_list(data.get("experience"))
    normalized_data["certifications"] = clean_list(data.get("certifications"))
    normalized_data["responsibilities"] = clean_list(data.get("responsibilities"))
    normalized_data["keywords"] = clean_list(data.get("keywords"), is_keyword=True)
    
    normalized_data["raw_text"] = data.get("raw_text", "")
    
    return normalized_data

def parse_job_description(text: str) -> JobDescription:
    """
    Parse the raw job description text to extract structural sections like
    required/preferred skills, experience, education, certifications, and responsibilities.
    """
    if not isinstance(text, str):
        text = ""
        
    logger.info("job_parse_started")
    
    try:
        # 1. Clean and normalize raw text using cleaner utility
        cleaned_text = clean_text(text)
        
        # 2. Split into logical sections
        sections = split_sections(cleaned_text)
        logger.info("job_sections_detected", sections_keys=list(sections.keys()))
        
        # 3. Extract structured entities
        title = extract_job_title(cleaned_text)
        company = extract_company(cleaned_text)
        
        required_skills, preferred_skills = extract_skills(sections, cleaned_text)
        logger.info(
            "job_skills_extracted",
            required_count=len(required_skills),
            preferred_count=len(preferred_skills)
        )
        
        experience = extract_experience(sections, cleaned_text)
        education = extract_education(cleaned_text)
        certifications = extract_certifications(cleaned_text)
        responsibilities = extract_responsibilities(sections, cleaned_text)
        
        keywords = extract_keywords(
            skills=required_skills + preferred_skills,
            education=education,
            certifications=certifications,
            experience=experience,
            responsibilities=responsibilities
        )
        logger.info("job_keywords_generated", keywords_count=len(keywords))
        
        # 4. Assemble dict and Normalize output
        extracted_dict = {
            "title": title,
            "company": company,
            "required_skills": required_skills,
            "preferred_skills": preferred_skills,
            "education": education,
            "experience": experience,
            "certifications": certifications,
            "responsibilities": responsibilities,
            "keywords": keywords,
            "raw_text": text  # Preserve original raw_text
        }
        
        normalized_dict = normalize_job_description(extracted_dict)
        
        # 5. Return JobDescription schema
        job_desc = JobDescription.model_validate(normalized_dict)
        
        logger.info("job_parse_completed", title=job_desc.title, company=job_desc.company)
        return job_desc
        
    except Exception as e:
        logger.error("job_parse_failed", error=str(e))
        raise e
