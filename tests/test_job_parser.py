import os
import pytest
from app.services.job_match.parser import (
    parse_job_description,
    split_sections,
    extract_job_title,
    extract_company,
    extract_skills,
    extract_experience,
    extract_education,
    extract_certifications,
    extract_responsibilities,
    extract_keywords,
    normalize_job_description,
)
from app.schemas.job_match import JobDescription

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "job_descriptions")

def load_fixture(filename: str) -> str:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# --- Fixture Tests ---

def test_software_engineer_fixture_title():
    text = load_fixture("software_engineer.txt")
    job_desc = parse_job_description(text)
    assert job_desc.title == "Software Engineer"

def test_software_engineer_fixture_company():
    text = load_fixture("software_engineer.txt")
    job_desc = parse_job_description(text)
    assert job_desc.company == "Tech Solutions Inc."

def test_software_engineer_fixture_skills():
    text = load_fixture("software_engineer.txt")
    job_desc = parse_job_description(text)
    # Check required skills (lowercased comparison but display casing preserved)
    assert "Python" in job_desc.required_skills
    assert "Git" in job_desc.required_skills
    # Check preferred skills
    assert "Docker" in job_desc.preferred_skills
    assert "AWS" in job_desc.preferred_skills

def test_software_engineer_fixture_experience():
    text = load_fixture("software_engineer.txt")
    job_desc = parse_job_description(text)
    assert len(job_desc.experience) > 0
    assert any("3 years" in exp for exp in job_desc.experience)

def test_software_engineer_fixture_education():
    text = load_fixture("software_engineer.txt")
    job_desc = parse_job_description(text)
    assert "Bachelor" in job_desc.education

def test_software_engineer_fixture_certifications():
    text = load_fixture("software_engineer.txt")
    job_desc = parse_job_description(text)
    assert "AWS" in job_desc.certifications

def test_software_engineer_fixture_responsibilities():
    text = load_fixture("software_engineer.txt")
    job_desc = parse_job_description(text)
    assert len(job_desc.responsibilities) == 4
    assert "Design, build, and maintain efficient, reusable, and reliable code." in job_desc.responsibilities

def test_ml_engineer_fixture_title():
    text = load_fixture("ml_engineer.txt")
    job_desc = parse_job_description(text)
    assert job_desc.title == "Machine Learning Engineer"

def test_ml_engineer_fixture_skills():
    text = load_fixture("ml_engineer.txt")
    job_desc = parse_job_description(text)
    assert "PyTorch" in job_desc.required_skills
    assert "spaCy" in job_desc.preferred_skills
    assert "TensorFlow" in job_desc.preferred_skills

def test_data_scientist_fixture_company():
    text = load_fixture("data_scientist.txt")
    job_desc = parse_job_description(text)
    assert job_desc.company == "DataCorp Analytics"

def test_backend_python_fixture_all():
    text = load_fixture("backend_python.txt")
    job_desc = parse_job_description(text)
    assert job_desc.title == "Backend Python Developer"
    assert job_desc.company == "PyTech Global"
    assert "FastAPI" in job_desc.required_skills
    assert "Django" in job_desc.preferred_skills
    assert "B.Tech" in job_desc.education
    assert "BE" in job_desc.education
    assert "Kubernetes" in job_desc.certifications

# --- Helper Component Tests ---

def test_extract_job_title_from_heading():
    text = "# Lead Architect\nPosition: Dev\nRole: Dev2"
    assert extract_job_title(text) == "Lead Architect"

def test_extract_job_title_from_position():
    text = "Position: Senior Staff Engineer\nRole: Lead"
    assert extract_job_title(text) == "Senior Staff Engineer"

def test_extract_job_title_from_role():
    text = "Role: DevOps Engineer\nJob Title: Architect"
    assert extract_job_title(text) == "DevOps Engineer"

def test_extract_job_title_from_job_title():
    text = "Job Title: Cloud Architect"
    assert extract_job_title(text) == "Cloud Architect"

def test_extract_job_title_fallback():
    text = "\n\nFirst Non-Empty Line Here\nSome description."
    assert extract_job_title(text) == "First Non-Empty Line Here"

def test_extract_company_various():
    assert extract_company("Company: Google Inc.") == "Google Inc."
    assert extract_company("Employer: Microsoft") == "Microsoft"
    assert extract_company("About Company: Meta Platforms") == "Meta Platforms"
    assert extract_company("Hiring Company: Netflix") == "Netflix"
    assert extract_company("Random Text without company") is None

def test_extract_skills_preferred_vs_required():
    sections = {
        "required_skills": "We need Python and SQL.",
        "preferred_skills": "Pluses: Docker, Kubernetes",
        "general_skills": "Skills: Git"
    }
    req, pref = extract_skills(sections, "")
    assert "Python" in req
    assert "SQL" in req
    assert "Git" in req
    assert "Docker" in pref
    assert "Kubernetes" in pref

def test_extract_skills_fallback_full_text():
    # No skills sections listed, should parse entire text and put all in required_skills
    sections = {
        "intro": "We are seeking a Python and Docker developer."
    }
    req, pref = extract_skills(sections, "We are seeking a Python and Docker developer.")
    assert "Python" in req
    assert "Docker" in req
    assert len(pref) == 0

def test_extract_experience_patterns():
    sections = {
        "experience": "- 3 years of Python\n- Minimum 5 years of Docker\n- 2-4 years in industry"
    }
    exp = extract_experience(sections, "")
    assert len(exp) == 3
    assert "3 years of Python" in exp
    assert "Minimum 5 years of Docker" in exp
    assert "2-4 years in industry" in exp

def test_extract_education_degrees():
    text = "Requires B.Tech or MS, MS, PhD preferred, Bachelor degree acceptable"
    edu = extract_education(text)
    assert "B.Tech" in edu
    assert "MS" in edu
    assert "PhD" in edu
    assert "Bachelor" in edu

def test_extract_certifications():
    text = "AWS Certified Architect, Kubernetes CKA, Docker Associate"
    certs = extract_certifications(text)
    assert "AWS" in certs
    assert "Kubernetes" in certs
    assert "Docker" in certs

def test_extract_responsibilities_bullets():
    sections = {
        "responsibilities": "- Write clean code\n* Build scalable web APIs\n1. Maintain databases"
    }
    resp = extract_responsibilities(sections, "")
    assert len(resp) == 3
    assert resp[0] == "Write clean code"
    assert resp[1] == "Build scalable web APIs"
    assert resp[2] == "Maintain databases"

def test_extract_keywords_combination():
    skills = ["Python", "FastAPI"]
    education = ["B.Tech"]
    certifications = ["AWS"]
    experience = ["3 years of experience with Python"]
    responsibilities = ["Build API endpoints and manage databases"]
    keywords = extract_keywords(
        skills=skills,
        education=education,
        certifications=certifications,
        experience=experience,
        responsibilities=responsibilities
    )
    # Should contain lowercased and sorted keywords
    assert "python" in keywords
    assert "fastapi" in keywords
    assert "b.tech" in keywords
    assert "aws" in keywords
    assert "experience" in keywords
    assert "api" in keywords
    assert "databases" in keywords

# --- Edge Cases & Normalization Tests ---

def test_empty_job_description():
    job_desc = parse_job_description("")
    assert job_desc.title is None
    assert job_desc.company is None
    assert job_desc.required_skills == []
    assert job_desc.preferred_skills == []
    assert job_desc.education == []
    assert job_desc.experience == []
    assert job_desc.certifications == []
    assert job_desc.responsibilities == []
    assert job_desc.keywords == []
    assert job_desc.raw_text == ""

def test_poorly_formatted_job_description():
    # A single sentence with no headings
    text = "We are hiring a Python Backend Engineer at Google who has 5 years of Docker and AWS certifications."
    job_desc = parse_job_description(text)
    assert job_desc.title == "We are hiring a Python Backend Engineer at Google who has 5 years of Docker and AWS certifications."
    assert job_desc.company is None
    assert "Python" in job_desc.required_skills
    assert "Docker" in job_desc.required_skills
    assert "AWS" in job_desc.certifications
    assert any("5 years" in exp for exp in job_desc.experience)

def test_normalization_rules():
    raw_data = {
        "title": "  Software   Engineer  ",
        "company": "Tech \u00a0 Corp",
        "required_skills": ["python", "Python", "fastapi"],
        "preferred_skills": ["AWS", "aws", "docker"],
        "education": ["B.Tech", "b.tech"],
        "experience": ["3 years", "3   years"],
        "certifications": ["AWS", "Aws"],
        "responsibilities": ["Coding", "  Coding  "],
        "keywords": ["Python", "FastAPI"],
        "raw_text": "Original Raw Text"
    }
    norm = normalize_job_description(raw_data)
    assert norm["title"] == "Software Engineer"
    assert norm["company"] == "Tech Corp"
    # Duplicate skills removed, sorted alphabetically (case-insensitive)
    assert norm["required_skills"] == ["FastAPI", "Python"]
    assert norm["preferred_skills"] == ["AWS", "Docker"]
    assert norm["education"] == ["B.Tech"]
    assert norm["experience"] == ["3 years"]
    assert norm["certifications"] == ["AWS"]
    assert norm["responsibilities"] == ["Coding"]
    # Keywords are lowercased and sorted
    assert norm["keywords"] == ["fastapi", "python"]
    assert norm["raw_text"] == "Original Raw Text"

def test_no_none_values_in_lists():
    job_desc = parse_job_description("Software Engineer at Google\nPython\n3 years experience")
    assert job_desc.required_skills is not None
    assert isinstance(job_desc.required_skills, list)
    assert all(x is not None for x in job_desc.required_skills)
    assert all(x is not None for x in job_desc.preferred_skills)
    assert all(x is not None for x in job_desc.education)
    assert all(x is not None for x in job_desc.experience)
    assert all(x is not None for x in job_desc.certifications)
    assert all(x is not None for x in job_desc.responsibilities)
    assert all(x is not None for x in job_desc.keywords)
