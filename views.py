from pathlib import Path
import json
import os
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube
from .models import BlogPost
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

# Initialize Google Generative AI
genai.configure(api_key=settings.GOOGLE_API_KEY)

@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data.get('link')
            
            if not yt_link:
                return JsonResponse({'error': 'YouTube link is missing'}, status=400)

            transcription = get_transcription(yt_link)
            if not transcription:
                return JsonResponse({'error': 'Failed to get transcription'}, status=500)

            blog_content = generate_blog_from_transcription(transcription)
            if not blog_content:
                return JsonResponse({'error': 'Failed to generate blog article'}, status=500)

            try:
                new_blog_article = BlogPost.objects.create(
                    user=request.user,
                    youtube_link=yt_link,
                    generated_content=blog_content,
                )
                new_blog_article.save()
            except Exception as e:
                print(f"Error saving blog article: {e}")
                return JsonResponse({'error': f'Failed to save blog article: {str(e)}'}, status=500)

            return JsonResponse({'content': blog_content})

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)
        except Exception as e:
            print(f"Unexpected error: {e}")
            return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def get_transcription(link):
    try:
        video_id = extract_video_id(link)
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        transcription = ' '.join([entry['text'] for entry in transcript])
        print(f"Transcription obtained: {transcription[:100]}...")
        return transcription
    except Exception as e:
        print(f"Error during transcription: {e}")
        return None

def generate_blog_from_transcription(transcription):
    try:
        prompt = """You are a YouTube video summarizer. You will be taking the transcript text
                    and summarizing the entire video and providing the important summary in points
                    within 250 words. Please provide the summary of the text given here: """

        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt + transcription)
        generated_content = response.text
        print(f"Final summarized content: {generated_content[:100]}...")
        return generated_content if generated_content else None
    except Exception as e:
        print(f"Error during summarization: {e}")
        return None

def extract_video_id(url):
    import re
    video_id_match = re.search(r'v=([^&]+)', url)
    return video_id_match.group(1) if video_id_match else None

def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    try:
        blog_article_detail = BlogPost.objects.get(id=pk)
        if request.user == blog_article_detail.user:
            return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
        else:
            return redirect('/')
    except BlogPost.DoesNotExist:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = 'Invalid username or password'
            return render(request, 'login.html', {'error_message': error_message})
    
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeat_password = request.POST['repeat_password']

        if password == repeat_password:
            try:
                user = user.objects.create_user(username=username, email=email, password=password)
                user.save()
                login(request, user)
                return redirect('index')
            except IntegrityError:
                return render(request, 'signup.html', {'error_message': 'Username or email already exists'})
            except Exception as e:
                return render(request, 'signup.html', {'error_message': f'Error creating account: {e}'})
        else:
            return render(request, 'signup.html', {'error_message': 'Passwords do not match'})
    
    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')
