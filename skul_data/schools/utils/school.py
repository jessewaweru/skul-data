from django.utils import timezone
from skul_data.schools.models.school import School


def get_current_term(school_id=None, school=None):
    """
    Get current term information for a school.
    Can accept either school_id or school instance.
    Returns None if no current term is active.
    """
    try:
        if school is None and school_id is not None:
            school = School.objects.get(id=school_id)
        elif school is None:
            raise ValueError("Either school_id or school must be provided")

        today = timezone.now().date()

        if not all([school.current_term, school.term_start_date, school.term_end_date]):
            return None

        if school.term_start_date <= today <= school.term_end_date:
            return {
                "term": school.current_term,
                "start_date": school.term_start_date,
                "end_date": school.term_end_date,
                "year": school.current_school_year,
            }
        return None
    except School.DoesNotExist:
        return None
