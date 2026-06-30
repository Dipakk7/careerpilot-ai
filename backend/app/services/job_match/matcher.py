import re
from datetime import datetime

DEGREE_RANKS = {
    "phd": 3,
    "doctor": 3,
    "master": 2,
    "ms": 2,
    "m.tech": 2,
    "mtech": 2,
    "mba": 2,
    "mca": 2,
    "bachelor": 1,
    "bs": 1,
    "b.tech": 1,
    "btech": 1,
    "be": 1,
    "bca": 1,
    "diploma": 0
}

def get_degree_rank(degree_str: str) -> int:
    if not degree_str:
        return -1
    d_lower = degree_str.lower().replace(".", "").strip()
    for key, rank in DEGREE_RANKS.items():
        # Match exact word or substring
        pattern = rf"\b{re.escape(key.replace('.', ''))}\b"
        if re.search(pattern, d_lower):
            return rank
    # Fallback to simple substring match if word boundary didn't hit
    for key, rank in DEGREE_RANKS.items():
        if key in d_lower:
            return rank
    return -1

def calculate_experience_years(duration_str: str) -> float:
    if not duration_str or not isinstance(duration_str, str):
        return 0.0
    duration_str = duration_str.strip()
    if not duration_str:
        return 0.0
    
    # Check for direct duration strings
    m_yrs = re.search(r"(\d+(?:\.\d+)?)\s*(?:yr|year)s?", duration_str, re.IGNORECASE)
    if m_yrs:
        return float(m_yrs.group(1))
    m_mos = re.search(r"(\d+(?:\.\d+)?)\s*(?:month|mo)s?", duration_str, re.IGNORECASE)
    if m_mos:
        return float(m_mos.group(1)) / 12.0

    # Date range parsing (e.g. "Jan 2020 - Dec 2022")
    parts = re.split(r'\s*(?:-|–|—|to|till)\s*', duration_str)
    if len(parts) == 2:
        start_str, end_str = parts[0].strip(), parts[1].strip()
        
        def parse_date(d_str: str, is_end: bool = False):
            d_str_lower = d_str.lower()
            if d_str_lower in ("present", "current", "now", ""):
                # Use current date or fixed mock date for reproducibility in tests (June 2026)
                now = datetime.now()
                return now.year, now.month
            
            m_ym = re.search(r"(\d{4})-(\d{2})", d_str)
            if m_ym:
                return int(m_ym.group(1)), int(m_ym.group(2))
                
            m_my = re.search(r"(\d{1,2})[/-](\d{4})", d_str)
            if m_my:
                return int(m_my.group(2)), int(m_my.group(1))
                
            m_y = re.search(r"(\d{4})", d_str)
            if m_y:
                return int(m_y.group(1)), 12 if is_end else 1
                
            return None
            
        start_parsed = parse_date(start_str, is_end=False)
        end_parsed = parse_date(end_str, is_end=True)
        
        if start_parsed and end_parsed:
            sy, sm = start_parsed
            ey, em = end_parsed
            months = (ey - sy) * 12 + (em - sm)
            return max(0.0, (months + 1) / 12.0)
            
    m_y = re.findall(r"\b(\d{4})\b", duration_str)
    if len(m_y) == 2:
        sy, ey = int(m_y[0]), int(m_y[1])
        return float(max(0, ey - sy))
    elif len(m_y) == 1:
        return 1.0
        
    return 0.0

def extract_years_required(job_exp: list[str]) -> float:
    max_years = 0.0
    for s in job_exp:
        # Check "3+ years", "5 years"
        m_yrs = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:year|yr)s?", s, re.IGNORECASE)
        if m_yrs:
            val = float(m_yrs.group(1))
            if val > max_years:
                max_years = val
        # Check "minimum 4 years"
        m_min = re.search(r"minimum\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:year|yr)s?", s, re.IGNORECASE)
        if m_min:
            val = float(m_min.group(1))
            if val > max_years:
                max_years = val
    return max_years

def match_skills(
    resume_skills: list[str],
    required_skills: list[str],
    preferred_skills: list[str]
) -> dict:
    """
    Match resume skills against job description required and preferred skills.
    Normalize all skills, case-insensitive, removing duplicates.
    """
    # Normalize: lowercase, stripped, non-empty, unique
    norm_resume = {s.strip().lower() for s in resume_skills if s and s.strip()}
    norm_required = {s.strip().lower() for s in required_skills if s and s.strip()}
    norm_preferred = {s.strip().lower() for s in preferred_skills if s and s.strip()}
    
    # Map lowercase normalized skills back to their display casing for return lists
    casing_map = {}
    for s in resume_skills + required_skills + preferred_skills:
        if s and s.strip():
            casing_map[s.strip().lower()] = s.strip()
            
    matched_req_set = norm_resume.intersection(norm_required)
    missing_req_set = norm_required.difference(norm_resume)
    matched_pref_set = norm_resume.intersection(norm_preferred)
    missing_pref_set = norm_preferred.difference(norm_resume)
    extra_set = norm_resume.difference(norm_required.union(norm_preferred))
    
    # Calculate score
    req_ratio = len(matched_req_set) / len(norm_required) if norm_required else 1.0
    pref_ratio = len(matched_pref_set) / len(norm_preferred) if norm_preferred else 1.0
    
    req_score = req_ratio * 80.0
    pref_score = pref_ratio * 20.0
    
    # Missing required skills penalize heavily (e.g., 10 points per missing required skill)
    penalty = 10.0 * len(missing_req_set)
    skills_score = max(0, min(100, int(req_score + pref_score - penalty + 0.5)))
    
    # Map back to display casing
    return {
        "matched_required": sorted([casing_map[s] for s in matched_req_set]),
        "missing_required": sorted([casing_map[s] for s in missing_req_set]),
        "matched_preferred": sorted([casing_map[s] for s in matched_pref_set]),
        "missing_preferred": sorted([casing_map[s] for s in missing_pref_set]),
        "extra_skills": sorted([casing_map[s] for s in extra_set]),
        "score": skills_score
    }

def match_experience(resume_experience: list[dict], job_experience: list[str]) -> dict:
    """
    Match resume experience against job description experience requirements.
    Supports parsing durations like 2 years, 3+ years, 5 years, Minimum 4 years.
    """
    target_required_years = extract_years_required(job_experience)
    
    total_resume_years = 0.0
    for entry in resume_experience:
        dur = entry.get("duration") or ""
        total_resume_years += calculate_experience_years(dur)
        
    if target_required_years <= 0:
        matched = True
        experience_score = 100
        missing = []
    else:
        matched = total_resume_years >= target_required_years
        if matched:
            experience_score = 100
            missing = []
        else:
            # Score matches ratio, clamp below 100
            experience_score = max(0, min(99, int((total_resume_years / target_required_years) * 100 + 0.5)))
            missing = [f"Requires {target_required_years:.1f} years of experience, but resume only shows {total_resume_years:.1f} years."]
            
    return {
        "experience_score": experience_score,
        "matched": matched,
        "missing": missing,
        "details": {
            "required_years": target_required_years,
            "candidate_years": round(total_resume_years, 2)
        }
    }

def match_education(resume_education: list[dict], job_education: list[str]) -> dict:
    """
    Match resume education history against job description education requirements.
    Supports ranking degrees (Bachelor, Master, MBA, PhD, B.Tech, M.Tech, etc.)
    """
    if not job_education:
        return {
            "matched": True,
            "missing": [],
            "score": 100
        }
        
    # Get highest rank in resume education
    resume_ranks = []
    for entry in resume_education:
        deg = entry.get("degree")
        if deg:
            rank = get_degree_rank(deg)
            if rank != -1:
                resume_ranks.append(rank)
                
    highest_resume_rank = max(resume_ranks) if resume_ranks else -1
    
    # Get highest rank in job description education
    job_ranks = []
    for req in job_education:
        rank = get_degree_rank(req)
        if rank != -1:
            job_ranks.append(rank)
            
    highest_job_rank = max(job_ranks) if job_ranks else 1 # Default to Bachelor (1) if no recognized degrees
    
    if highest_resume_rank >= highest_job_rank:
        return {
            "matched": True,
            "missing": [],
            "score": 100
        }
    elif highest_resume_rank >= 0:
        # Partial match, calculate ratio and clamp
        score = max(0, min(99, int((highest_resume_rank / highest_job_rank) * 100)))
        return {
            "matched": False,
            "missing": job_education,
            "score": score
        }
    else:
        return {
            "matched": False,
            "missing": job_education,
            "score": 0
        }

def match_certifications(resume_certifications: list[str], job_certifications: list[str]) -> dict:
    """
    Match resume certifications against job description certifications.
    """
    # Normalize: lowercase, stripped, unique
    norm_resume = {c.strip().lower() for c in resume_certifications if c and c.strip()}
    norm_job = {c.strip().lower() for c in job_certifications if c and c.strip()}
    
    casing_map = {}
    for c in resume_certifications + job_certifications:
        if c and c.strip():
            casing_map[c.strip().lower()] = c.strip()
    if not norm_job:
        return {
            "matched": [],
            "missing": [],
            "extra": sorted([casing_map[c] for c in norm_resume]),
            "score": 100
        }
        
    matched_job_norms = set()
    matched_resume_norms = set()
    for jc in norm_job:
        for rc in norm_resume:
            if jc in rc or rc in jc:
                matched_job_norms.add(jc)
                matched_resume_norms.add(rc)
                break
                
    missing_job_norms = norm_job - matched_job_norms
    extra_resume_norms = norm_resume - matched_resume_norms
    
    score = int((len(matched_job_norms) / len(norm_job)) * 100 + 0.5)
    
    # Map matched_job_norms to the matched certifications of the resume (since they were present in resume)
    # or to the job certification name. It's safer to map to the original name in resume.
    # Wait, let's map matched_job_norms to the casing_map to keep it simple.
    return {
        "matched": sorted([casing_map[rc] for rc in matched_resume_norms]),
        "missing": sorted([casing_map[jc] for jc in missing_job_norms]),
        "extra": sorted([casing_map[rc] for rc in extra_resume_norms]),
        "score": score
    }

def match_keywords(resume_keywords: list[str], job_keywords: list[str]) -> dict:
    """
    Match resume keywords against job description keywords.
    """
    norm_resume = {k.strip().lower() for k in resume_keywords if k and k.strip()}
    norm_job = {k.strip().lower() for k in job_keywords if k and k.strip()}
    
    casing_map = {}
    for k in resume_keywords + job_keywords:
        if k and k.strip():
            casing_map[k.strip().lower()] = k.strip()
            
    if not norm_job:
        return {
            "matched_keywords": [],
            "missing_keywords": [],
            "keyword_score": 100
        }
        
    matched_set = norm_resume.intersection(norm_job)
    missing_set = norm_job.difference(norm_resume)
    
    score = int((len(matched_set) / len(norm_job)) * 100 + 0.5)
    
    return {
        "matched_keywords": sorted([casing_map[k] for k in matched_set]),
        "missing_keywords": sorted([casing_map[k] for k in missing_set]),
        "keyword_score": score
    }

