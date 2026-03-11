from pymongo import MongoClient
import os

client = MongoClient(os.environ.get("MONGO_URI"))
db = client["lms_db"]

users_collection = db["users"]
classrooms_collection = db["classrooms"]
study_materials_collection = db["study_materials"]
videos_collection = db["videos"]
questions_collection = db["questions"]
student_results_collection = db["student_results"]
community_posts_collection = db["community_posts"]
assignments_collection = db["assignments"]
assignment_submissions_collection = db["assignment_submissions"]
live_classes_collection = db["live_classes"]
print("MONGO_URI:", os.environ.get("MONGO_URI"))