#!/usr/bin/env python3
"""
Script to seed initial job data into MongoDB
"""

import asyncio
import motor.motor_asyncio
from datetime import datetime
import os

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL)
db = client.hexagon
jobs_collection = db.jobs

# Sample job data
sample_jobs = [
    {
        "title": "Senior Software Engineer",
        "company": "Tech Corp",
        "location": "San Francisco, CA",
        "experience": "Senior",
        "skills": ["Python", "React", "AWS", "Docker", "Kubernetes", "PostgreSQL"],
        "description": "We are looking for a senior software engineer to join our team and help build next-generation applications.\n\nKey Responsibilities:\n• Design and develop scalable web applications\n• Lead technical discussions and mentor junior developers\n• Collaborate with cross-functional teams to deliver high-quality software\n• Implement best practices for code quality and performance\n• Work with modern technologies including React, Python, and AWS\n\nRequirements:\n• 5+ years of experience in software development\n• Strong proficiency in Python and React\n• Experience with cloud platforms (AWS preferred)\n• Knowledge of containerization technologies (Docker, Kubernetes)\n• Excellent problem-solving and communication skills\n\nWe offer competitive salary, comprehensive benefits, and opportunities for professional growth in a dynamic, innovative environment.",
        "user_id": "admin",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    },
    {
        "title": "Frontend Developer",
        "company": "StartupXYZ",
        "location": "Remote",
        "experience": "Mid",
        "skills": ["React", "TypeScript", "Node.js", "CSS", "JavaScript"],
        "description": "Join our growing frontend team to build amazing user experiences for millions of users worldwide.\n\nWhat You'll Do:\n• Build responsive, interactive web applications using React and TypeScript\n• Collaborate with designers to implement pixel-perfect UI components\n• Optimize applications for maximum speed and scalability\n• Write clean, maintainable code following best practices\n• Participate in code reviews and contribute to technical decisions\n\nRequirements:\n• 3+ years of frontend development experience\n• Strong expertise in React and TypeScript\n• Experience with modern CSS frameworks and methodologies\n• Knowledge of Node.js and backend integration\n• Excellent attention to detail and user experience\n\nJoin us in building the future of web applications with cutting-edge technologies and a passionate team.",
        "user_id": "admin",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    },
    {
        "title": "Full Stack Developer",
        "company": "Enterprise Inc",
        "location": "New York, NY",
        "experience": "Senior",
        "skills": ["Java", "Spring Boot", "React", "PostgreSQL", "Redis", "Docker"],
        "description": "Looking for a full stack developer with strong backend experience to join our enterprise development team.\n\nRole Overview:\n• Design and implement end-to-end solutions using Java and React\n• Build robust APIs and microservices using Spring Boot\n• Work with databases, caching systems, and message queues\n• Ensure application security and performance optimization\n• Mentor team members and contribute to technical architecture decisions\n\nTechnical Requirements:\n• 5+ years of full stack development experience\n• Expertise in Java, Spring Boot, and React\n• Strong database design and optimization skills (PostgreSQL)\n• Experience with caching solutions (Redis) and containerization (Docker)\n• Knowledge of enterprise-grade application development\n\nWe provide excellent benefits, professional development opportunities, and the chance to work on large-scale enterprise applications serving thousands of users.",
        "user_id": "admin",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    },
    {
        "title": "DevOps Engineer",
        "company": "Cloud Solutions Ltd",
        "location": "Austin, TX",
        "experience": "Mid",
        "skills": ["AWS", "Terraform", "Jenkins", "Python", "Linux", "Docker"],
        "description": "We're seeking a DevOps Engineer to help automate our infrastructure and streamline our development processes.\n\nResponsibilities:\n• Design and maintain CI/CD pipelines using Jenkins and AWS\n• Automate infrastructure provisioning using Terraform\n• Monitor and optimize application performance and reliability\n• Implement security best practices across all environments\n• Collaborate with development teams to improve deployment processes\n\nSkills Required:\n• 3+ years of DevOps/Infrastructure experience\n• Strong knowledge of AWS services and cloud architecture\n• Experience with Infrastructure as Code (Terraform preferred)\n• Proficiency in scripting languages (Python, Bash)\n• Understanding of containerization and orchestration\n\nJoin our team and help us build scalable, reliable infrastructure that powers our growing business.",
        "user_id": "admin",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    },
    {
        "title": "Product Manager",
        "company": "Innovation Hub",
        "location": "Seattle, WA",
        "experience": "Senior",
        "skills": ["Product Strategy", "Agile", "Analytics", "User Research", "Roadmapping"],
        "description": "Lead product strategy and execution for our flagship products serving over 1 million users globally.\n\nKey Responsibilities:\n• Define product vision and strategy aligned with business objectives\n• Work closely with engineering, design, and marketing teams\n• Conduct user research and analyze market trends\n• Create and maintain product roadmaps and feature specifications\n• Use data analytics to drive product decisions and measure success\n\nQualifications:\n• 5+ years of product management experience\n• Strong analytical skills and data-driven decision making\n• Experience with Agile methodologies and cross-functional team leadership\n• Excellent communication and stakeholder management skills\n• Background in user research and product analytics tools\n\nBe part of a team that's reshaping how users interact with technology through innovative product experiences.",
        "user_id": "admin",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    },
    {
        "title": "Data Scientist",
        "company": "Analytics Pro",
        "location": "Boston, MA",
        "experience": "Mid",
        "skills": ["Python", "Machine Learning", "SQL", "TensorFlow", "Statistics", "R"],
        "description": "Join our data science team to extract insights from large datasets and build predictive models that drive business decisions.\n\nWhat You'll Do:\n• Analyze complex datasets to identify trends and patterns\n• Build and deploy machine learning models using Python and TensorFlow\n• Create data visualizations and reports for stakeholders\n• Collaborate with engineering teams to productionize models\n• Stay current with latest developments in data science and ML\n\nRequirements:\n• 3+ years of data science experience\n• Strong programming skills in Python and SQL\n• Experience with machine learning frameworks (TensorFlow, scikit-learn)\n• Statistical analysis and hypothesis testing knowledge\n• Excellent problem-solving and communication skills\n\nWork with cutting-edge data science technologies and make a real impact on our business outcomes.",
        "user_id": "admin",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
]

async def seed_jobs():
    """Seed the database with sample job data"""
    try:
        # Clear existing jobs
        await jobs_collection.delete_many({})
        print("Cleared existing jobs")
        
        # Insert sample jobs
        result = await jobs_collection.insert_many(sample_jobs)
        print(f"Inserted {len(result.inserted_ids)} jobs")
        
        # Verify insertion
        count = await jobs_collection.count_documents({})
        print(f"Total jobs in database: {count}")
        
    except Exception as e:
        print(f"Error seeding jobs: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    print("Seeding job data...")
    asyncio.run(seed_jobs())
    print("Seeding completed!")
