from django.shortcuts import render
from .forms import ChatQuestionForm, ResourceFinderForm
from .services import ask_rag, find_resources, normalize_rag_response

def home(request): return render(request, "relief/home.html")

def chat(request):
    form = ChatQuestionForm(request.POST or None); response = None
    if request.method == "POST" and form.is_valid():
        response = normalize_rag_response(ask_rag(form.cleaned_data["question"]))
    return render(request, "relief/chat.html", {"form": form, "response": response})

def resource_finder(request):
    form = ResourceFinderForm(request.GET or None); results = None
    if form.is_valid():
        results = find_resources(form.cleaned_data["location"], form.cleaned_data["need"], form.cleaned_data["constraints"])
    return render(request, "relief/resource_finder.html", {"form": form, "results": results})
