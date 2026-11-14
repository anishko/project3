from django.shortcuts import render
from .forms import ResourceFinderForm
from .services import find_resources

def home(request): return render(request, "relief/home.html")

def resource_finder(request):
    form = ResourceFinderForm(request.GET or None); results = None
    if form.is_valid():
        results = find_resources(form.cleaned_data["location"], form.cleaned_data["need"], form.cleaned_data["constraints"])
    return render(request, "relief/resource_finder.html", {"form": form, "results": results})
