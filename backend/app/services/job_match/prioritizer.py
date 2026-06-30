def prioritize_gaps(
    skill_gap: dict,
    experience_gap: dict,
    education_gap: dict,
    certification_gap: dict,
    keyword_gap: dict,
    resume: any = None
) -> list[dict]:
    """
    Generate prioritized improvements list from all gaps.
    Priority Rules:
    - HIGH: Required skills, Missing experience, Missing degree
    - MEDIUM: Preferred skills, Certifications
    - LOW: Keywords, Formatting
    """
    improvements = []
    
    # --- HIGH PRIORITY ---
    # 1. Required skills
    for skill in skill_gap.get("missing_required", []):
        improvements.append({
            "priority": "HIGH",
            "category": "skills",
            "message": f"Add missing required skill: {skill}"
        })
        
    # 2. Missing experience
    if not experience_gap.get("matched", True):
        req = experience_gap.get("required", "0.0 years")
        res_years = experience_gap.get("resume", "0.0 years")
        msg = f"Requires {req} of experience, but resume only shows {res_years}."
        improvements.append({
            "priority": "HIGH",
            "category": "experience",
            "message": msg
        })
        
    # 3. Missing degree
    if not education_gap.get("matched", True):
        req = education_gap.get("required", "")
        msg = f"Missing required education level (Requires: {req})"
        improvements.append({
            "priority": "HIGH",
            "category": "education",
            "message": msg
        })
        
    # --- MEDIUM PRIORITY ---
    # 1. Preferred skills
    for skill in skill_gap.get("missing_preferred", []):
        improvements.append({
            "priority": "MEDIUM",
            "category": "skills",
            "message": f"Add missing preferred skill: {skill}"
        })
        
    # 2. Certifications
    for cert in certification_gap.get("missing", []):
        improvements.append({
            "priority": "MEDIUM",
            "category": "certifications",
            "message": f"Consider obtaining certification: {cert}"
        })
        
    # --- LOW PRIORITY ---
    # 1. Keywords
    for kw in keyword_gap.get("missing", []):
        improvements.append({
            "priority": "LOW",
            "category": "keywords",
            "message": f"Incorporate keyword: {kw}"
        })
        
    # 2. Formatting
    formatting_added = False
    if resume:
        # Check professional links
        data = getattr(resume, "parsed_data", {})
        if isinstance(data, dict) and "data" in data:
            resume_data = data["data"]
            links = resume_data.get("links", {})
            links_val = links.get("value", []) if isinstance(links, dict) else links
            if not links_val:
                improvements.append({
                    "priority": "LOW",
                    "category": "formatting",
                    "message": "Add professional links (LinkedIn, GitHub) to contact section."
                })
                formatting_added = True
                
        # Check raw text formatting issues
        raw_text = getattr(resume, "raw_text", "")
        if raw_text and ("\t" in raw_text or "   " in raw_text):
            improvements.append({
                "priority": "LOW",
                "category": "formatting",
                "message": "Fix layout spacing and alignment issues for ATS compliance."
            })
            formatting_added = True
            
    if not formatting_added:
        improvements.append({
            "priority": "LOW",
            "category": "formatting",
            "message": "Ensure resume formatting uses standard margins and simple, clean fonts."
        })
        
    # Remove duplicates preserving order
    seen = set()
    unique_improvements = []
    for item in improvements:
        key = (item["priority"], item["category"], item["message"].strip().lower())
        if key not in seen:
            seen.add(key)
            unique_improvements.append(item)
            
    # Sort: HIGH -> MEDIUM -> LOW
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    unique_improvements.sort(key=lambda x: priority_order.get(x["priority"], 3))
    
    return unique_improvements
