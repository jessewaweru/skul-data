from django.utils import timezone
from skul_data.schools.models.school import School


def get_current_term(school_id):
    try:
        school = School.objects.get(id=school_id)
        today = timezone.now().date()
        if (
            school.current_term
            and school.term_start_date
            and school.term_end_date
            and school.term_start_date <= today <= school.term_end_date
        ):
            return {
                "term": school.current_term,
                "start_date": school.term_start_date,
                "end_date": school.term_end_date,
                "year": school.current_school_year,
            }
        else:
            return None
    except School.DoesNotExist:
        return None
