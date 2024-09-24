from django.shortcuts import render

# Create your views here.

def index(request):
    return render(request, 'index.html')

def task(request):
    return render(request, 'task.html')

def task2(request):
    return render(request, 'task2.html')

def gettask(request):
    return render(request, 'gettask.html')

def about(request):
    return render(request, 'frontend/about.html')

def contact(request):
    return render(request, 'frontend/contact.html')

def login(request):
    return render(request, 'frontend/login.html')

def register(request):
    return render(request, 'frontend/register.html')    

def logout(request):
    return render(request, 'frontend/logout.html')

def dashboard(request):
    return render(request, 'frontend/dashboard.html')

def profile(request):
    return render(request, 'frontend/profile.html')
