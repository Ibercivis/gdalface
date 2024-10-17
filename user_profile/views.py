from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.models import User

# Create your views here.
def UserView(request):
    user = request.user
    if user.is_authenticated:
        time = user.userprofile.time_spent
        geo = user.userprofile.geoattempts_done
        cp = user.userprofile.controlPointsDone
        che = user.userprofile.cheating
        context = {
            'user': user,
            'time': time,
            'geo': geo,
            'cp': cp,
            'che': che,
        }
        return render(request, 'user.html', context)
    return render(request, 'user.html')

