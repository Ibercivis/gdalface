"""
Context processors for frontend app.
"""

def menu_context(request):
    """
    Adds menu-related context variables to all templates.
    """
    return {
        'is_homepage': request.path == '/',
        'current_path': request.path,
    }