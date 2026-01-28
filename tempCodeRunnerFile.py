from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
import time
import threading
from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from textblob import TextBlob
import spacy
from difflib import SequenceMatcher
import json