from skul_data.documents.models.document import DocumentCategory


def seed_document_categories():
    """
    Seeds the database with predefined school document categories.
    """
    categories = [
        # Administration & Operations
        (
            "Staff Contracts & Employment Letters",
            "HR and employment-related documentation.",
        ),
        (
            "Teacher & Staff Performance Reviews",
            "Annual and periodic staff evaluations.",
        ),
        ("Inventory Purchase Orders", "All purchase orders for school supplies."),
        ("Meeting Minutes", "Minutes from BOM, PTA, and internal meetings."),
        ("MOE Correspondence", "Official communications from Ministry of Education."),
        (
            "School Registration Certificate",
            "Accreditation and legal school documentation.",
        ),
        (
            "Fee Structures & Finance Reports",
            "Tuition, budget, and financial breakdowns.",
        ),
        ("Inspection Reports", "Education officers' audits and inspections."),
        # Student-Related
        ("Admission Forms", "New student registration and onboarding documents."),
        ("Birth Certificates / ID Copies", "Student identity verification."),
        ("Transfer Letters", "Student movements in/out of the school."),
        ("Report Cards", "Historical academic performance."),
        ("Disciplinary Records", "Reports of student misconduct and action taken."),
        ("Medical Records", "Optional medical details if submitted."),
        # Academic & Curriculum
        ("Scheme of Work / Lesson Plans", "Weekly and term teaching outlines."),
        ("Teaching Permits & Certificates", "Teacher qualification records."),
        ("Curriculum Changes", "MOE or internal updates to academic content."),
        ("Subject Department Reports", "Academic performance by department."),
        ("Marking Schemes", "Marking criteria and teacher notes."),
        # Parent & Community Involvement
        ("PTA Meeting Minutes", "Parent-Teacher Association reports."),
        ("Donor Letters", "Funding and support acknowledgment."),
        ("Sponsorship Agreements", "Student or school sponsorship contracts."),
        ("Community Outreach Reports", "Service and engagement activities."),
        # Infrastructure / Legal
        ("Building Plans", "Architectural layouts and blueprints."),
        ("Land Ownership Documents", "Title deeds or lease papers."),
        ("Insurance Documents", "Coverage for school property."),
        ("Fire & Health Inspection Certs", "Safety compliance certificates."),
    ]

    for name, description in categories:
        DocumentCategory.objects.get_or_create(
            name=name,
            defaults={"description": description, "is_custom": False},
        )

    print("✅ Document categories seeded successfully!")


# in shell

# from utils.document_categories import seed_document_categories
# seed_document_categories()
