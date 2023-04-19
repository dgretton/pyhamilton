# -*- coding: utf-8 -*-
"""
Created on Mon Apr 17 15:11:27 2023

@author: stefa
"""

import speech_recognition as sr
import pyttsx3

def voice_to_text():
    # Initialize the text-to-speech engine
    engine = pyttsx3.init()

    # Initialize the speech recognition engine
    r = sr.Recognizer()

    # Use the default microphone as the audio source
    with sr.Microphone() as source:
        print("Speak now!")
        audio = r.listen(source)

    # Use Google Speech Recognition to transcribe the audio
    try:
        text = r.recognize_google(audio)
        print(f"You said: {text}")

        # Speak the transcribed text
        engine.say(text)
        engine.runAndWait()
        return text
    except sr.UnknownValueError:
        print("Oops! Didn't catch that")
    except sr.RequestError as e:
        print(f"Uh oh! Couldn't request results from Google Speech Recognition service; {e}")

    return None
