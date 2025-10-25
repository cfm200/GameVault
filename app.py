from flask import Flask, request, jsonify, make_response, g
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from functools import wraps
import certifi
import os
import jwt
import datetime
import bcrypt


app = Flask(__name__)

# Load environment variables
load_dotenv()

# Connect to MongoDB Atlas
uri = os.getenv("MONGODB_URI")
client = MongoClient(uri, tlsCAFile=certifi.where())
db = client.GameVaultDB
games = db.games
users = db.users
blacklist = db.blacklist

app.config['SECRET_KEY'] = os.getenv("JWT_SECRET", "GameVaultSecretKey")

from flask import g

def decode_token_from_header():
    token = request.headers.get("x-access-token")
    if not token:
        return None, {"error": "Token missing"}, 401

    if blacklist.find_one({"token": token}):
        return None, {"error": "Token has been blacklisted"}, 401

    try:
        data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        return data, None, None
    except jwt.ExpiredSignatureError:
        return None, {"error": "Token expired"}, 401
    except jwt.InvalidTokenError:
        return None, {"error": "Invalid token"}, 401


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload, error, code = decode_token_from_header()
        if error:
            return make_response(jsonify(error), code)
        g.user = {
            "user_id": payload.get("user_id"),
            "username": payload.get("username"),
            "admin": payload.get("admin", False)
        }
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload, error, code = decode_token_from_header()
        if error:
            return make_response(jsonify(error), code)
        if not payload.get("admin", False):
            return make_response(jsonify({"error": "Admin privileges required"}), 403)
        g.user = {
            "user_id": payload.get("user_id"),
            "username": payload.get("username"),
            "admin": True
        }
        return f(*args, **kwargs)
    return decorated


@app.route("/api/v1.0/register", methods=["POST"])
def register():
    data = request.get_json()

    if not data or not data.get("username") or not data.get("password"):
        return make_response(jsonify({"error": "Username and password are required"}), 400)

    username = data["username"]
    password = data["password"].encode("utf-8")

    # Check if username already exists
    if users.find_one({"username": username}):
        return make_response(jsonify({"error": "Username already exists"}), 409)

    # Hash password
    hashed = bcrypt.hashpw(password, bcrypt.gensalt())

    new_user = {
        "username": username,
        "password": hashed,
        "admin": False
    }

    users.insert_one(new_user)
    return make_response(jsonify({"message": "User registered successfully"}), 201)


@app.route("/api/v1.0/login", methods=["POST"])
def login():
    # Try Basic Auth first
    auth = request.authorization
    if auth and auth.username and auth.password:
        user = users.find_one({"username": auth.username})
        if user and bcrypt.checkpw(auth.password.encode("utf-8"), user["password"]):
            token = jwt.encode({
                "user_id": str(user["_id"]),
                "username": user["username"],
                "admin": user.get("admin", False),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
            }, app.config["SECRET_KEY"], algorithm="HS256")
            return jsonify({"token": token})

        return make_response(jsonify({"error": "Invalid credentials"}), 401)

    # If not Basic Auth, fallback to JSON body
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return make_response(jsonify({"error": "Username and password required"}), 400)

    user = users.find_one({"username": data["username"]})
    if not user or not bcrypt.checkpw(data["password"].encode("utf-8"), user["password"]):
        return make_response(jsonify({"error": "Invalid credentials"}), 401)

    token = jwt.encode({
        "user_id": str(user["_id"]),
        "username": user["username"],
        "admin": user.get("admin", False),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    }, app.config["SECRET_KEY"], algorithm="HS256")

    return jsonify({"token": token})


@app.route("/api/v1.0/logout", methods=["POST"])
@token_required
def logout():
    token = request.headers.get("x-access-token")

    if blacklist.find_one({"token": token}):
        return make_response(jsonify({"message": "Token already blacklisted"}), 400)

    blacklist.insert_one({"token": token})
    return make_response(jsonify({"message": "Successfully logged out"}), 200)


# @app.route("/api/v1.0/protected-test", methods=["GET"])
# @token_required
# def protected_test():
#     return jsonify({"message": f"Hello {g.user['username']}"}), 200



# --------------------------------------------------------------------------------
# GET ALL GAMES
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games", methods=["GET"])
def show_all_games():
    # Read query params (string initially)
    page_num = request.args.get("pn", 1)
    page_size = request.args.get("ps", 10)

    # Validate pagination values
    try:
        page_num = int(page_num)
        page_size = int(page_size)
        if page_num < 1 or page_size < 1:
            return make_response(jsonify({"error": "Page number and page size must be positive integers"}), 400)
    except ValueError:
        return make_response(jsonify({"error": "Page number and Page size must be integers"}), 400)

    # Perform pagination
    page_start = (page_size * (page_num - 1))
    data_to_return = []

    for game in games.find().skip(page_start).limit(page_size):
        game["_id"] = str(game["_id"])
        for review in game["reviews"]:
            review["_id"] = str(review["_id"])
        data_to_return.append(game)

    return make_response(jsonify(data_to_return), 200)




# --------------------------------------------------------------------------------
# GET ONE GAME
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games/<string:id>", methods=["GET"])
def show_one_game(id):
    #check game ID format
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error":"Invalid Game ID format"}), 404)
    
    #convert id's to strings and return corresponding game
    game = games.find_one({'_id':ObjectId(id)})
    if game is not None:
        game["_id"] = str(game['_id'])
        for review in game['reviews']:
            review["_id"] = str(review["_id"])
        return make_response(jsonify(game), 200)
    else:
        return make_response(jsonify({"error" : "Invalid Game ID"}), 404)



# --------------------------------------------------------------------------------
# ADD NEW GAME
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games", methods=["POST"])
@admin_required
def add_new_game():

    if not request.is_json:
        return make_response(jsonify({"error": "Request must be JSON"}), 400)

    data = request.get_json()

    required_fields = ["title", "platforms", "release_year", "developer", "publisher", "esrb", "genres", "modes"]
    if not all(field in data for field in required_fields):
        return make_response(jsonify({"error": "Missing required fields"}), 400)

    # Check for duplicate title
    if games.find_one({"title": data["title"]}):
        return make_response(jsonify({"error": "A game with that title already exists"}), 409)

    new_game = {
        "title": data["title"],
        "platforms": data.get("platforms", []),
        "release_year": data.get("release_year"),
        "developer": data.get("developer"),
        "publisher": data.get("publisher"),
        "rating": data.get("rating", None),
        "esrb": data.get("esrb"),
        "genres": data.get("genres", []),
        "modes": data.get("modes", []),
        "reviews": [],
        "awards": []
    }

    # Optional geospatial validation
    hq = data.get("developer_hq")
    if hq:
        if (
            isinstance(hq, dict)
            and hq.get("type") == "Point"
            and isinstance(hq.get("coordinates"), list)
            and len(hq["coordinates"]) == 2
            and isinstance(hq["coordinates"][0], (int, float))
            and isinstance(hq["coordinates"][1], (int, float))
        ):
            new_game["developer_hq"] = hq
        else:
            return make_response(jsonify({"error": "Invalid GeoJSON format for developer_hq"}), 400)

    inserted_id = games.insert_one(new_game).inserted_id

    return make_response(jsonify({
        "message": "Game added successfully",
        "game_id": str(inserted_id)
    }), 201)




# --------------------------------------------------------------------------------
# EDIT GAME
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games/<string:id>", methods=["PUT"])
@admin_required
def edit_game(id):

    if not request.is_json:
        return make_response(jsonify({"error": "Request must be JSON"}), 400)

    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid Game ID format"}), 400)

    data = request.get_json()

    update_fields = {}

    for field in ["title", "platforms", "release_year", "developer", "publisher", "esrb", "genres", "modes"]:
        if field in data:
            update_fields[field] = data[field]

    if "developer_hq" in data:
        hq = data["developer_hq"]
        if (
            isinstance(hq, dict)
            and hq.get("type") == "Point"
            and isinstance(hq.get("coordinates"), list)
            and len(hq["coordinates"]) == 2
        ):
            update_fields["developer_hq"] = hq
        else:
            return make_response(jsonify({"error": "Invalid GeoJSON format"}), 400)

    if not update_fields:
        return make_response(jsonify({"error": "No valid update fields provided"}), 400)

    result = games.update_one({"_id": ObjectId(id)}, {"$set": update_fields})

    if result.modified_count == 1:
        return make_response(jsonify({"message": "Game updated successfully"}), 200)

    return make_response(jsonify({"error": "Game update failed"}), 500)




# --------------------------------------------------------------------------------
# DELETE GAME
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games/<string:id>", methods=["DELETE"])
@admin_required
def delete_game(id):

    # Validate ObjectId format
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid Game ID format"}), 400)
    
    result = games.delete_one({"_id": ObjectId(id)})
    
    if result.deleted_count == 1:
        return make_response(jsonify({}), 204)
    else:
        return make_response(jsonify({"error": "Invalid Game ID"}), 404)



# --------------------------------------------------------------------------------
# GET ALL REVIEWS FOR A GAME
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games/<string:id>/reviews", methods=["GET"])
def fetch_all_reviews(id):

    # Validate ObjectId format
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid Game ID format"}), 400)

    # Pagination parameters and validation
    page_num = request.args.get("pn", 1)
    page_size = request.args.get("ps", 10)

    try:
        page_num = int(page_num)
        page_size = int(page_size)
        if page_num < 1 or page_size < 1:
            return make_response(jsonify({"error": "Page number and page size must be positive integers"}), 400)
    except ValueError:
        return make_response(jsonify({"error": "Page number and page size must be integers"}), 400)

    # Calculate skip
    page_start = (page_size * (page_num - 1))

    # Retrieve game with reviews field only
    game = games.find_one({"_id": ObjectId(id)}, {"reviews": 1, "_id": 0})

    if not game:
        return make_response(jsonify({"error": "Invalid Game ID"}), 404)

    if "reviews" not in game or len(game["reviews"]) == 0:
        return make_response(jsonify({"error": "No reviews found"}), 404)

    # Convert ObjectId and apply pagination
    reviews = []
    for review in game["reviews"]:
        review["_id"] = str(review["_id"])
        reviews.append(review)

    paginated_reviews = reviews[page_start:page_start + page_size]

    return make_response(jsonify(paginated_reviews), 200)




# --------------------------------------------------------------------------------
# ADD NEW REVIEW FOR A GAME
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games/<string:g_id>/reviews", methods=["POST"])
@token_required
def add_new_review(g_id):

    if not ObjectId.is_valid(g_id):
        return make_response(jsonify({"error": "Invalid Game ID format"}), 400)

    if not request.is_json:
        return make_response(jsonify({"error": "Request must be JSON"}), 400)

    data = request.get_json()

    if "comment" not in data or "rating" not in data:
        return make_response(jsonify({"error": "Comment and rating are required"}), 400)

    try:
        rating = int(data["rating"])
        if rating < 1 or rating > 10:
            return make_response(jsonify({"error": "Rating must be between 1 and 10"}), 400)
    except ValueError:
        return make_response(jsonify({"error": "Rating must be a number"}), 400)

    game = games.find_one({"_id": ObjectId(g_id)})
    if not game:
        return make_response(jsonify({"error": "Game not found"}), 404)

    new_review = {
        "_id": ObjectId(),
        "user_id": g.user["user_id"],
        "username": g.user["username"],
        "comment": data["comment"],
        "rating": rating
    }

    games.update_one({"_id": ObjectId(g_id)}, {"$push": {"reviews": new_review}})

    return make_response(jsonify({"message": "Review added successfully"}), 201)




# --------------------------------------------------------------------------------
# GET ONE REVIEW FOR A GAME
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games/<string:g_id>/reviews/<string:r_id>", methods=["GET"])
def fetch_one_review(g_id, r_id):

    # Validate game ID format
    if not ObjectId.is_valid(g_id):
        return make_response(jsonify({"error": "Invalid Game ID format"}), 400)
    
    # Validate review ID format
    if not ObjectId.is_valid(r_id):
        return make_response(jsonify({"error": "Invalid Review ID format"}), 400)
    
    try:
        # First check if the game exists
        game = games.find_one({"_id": ObjectId(g_id)}, {"reviews": 1, "_id": 0})
        
        if game is None:
            return make_response(jsonify({"error": "Invalid Game ID"}), 404)
        
        # If game exists, check if review ID exists in it
        review = next((r for r in game.get("reviews", []) if str(r["_id"]) == r_id), None)
        
        if review is None:
            return make_response(jsonify({"error": "Invalid Review ID"}), 404)
        
        # Convert review _id to string for JSON serialization
        review["_id"] = str(review["_id"])
        
        return make_response(jsonify(review), 200)
    
    except Exception as e:
        # Handle any unexpected runtime errors
        return make_response(jsonify({"error": f"Server error: {str(e)}"}), 500)



# --------------------------------------------------------------------------------
# EDIT REVIEW
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games/<string:g_id>/reviews/<string:r_id>", methods=["PUT"])
@token_required
def edit_review(g_id, r_id):

    if not request.is_json:
        return make_response(jsonify({"error": "Request must be JSON"}), 400)

    if not ObjectId.is_valid(g_id) or not ObjectId.is_valid(r_id):
        return make_response(jsonify({"error": "Invalid ID format"}), 400)

    data = request.get_json()

    game = games.find_one({"_id": ObjectId(g_id)}, {"reviews": 1})
    if not game:
        return make_response(jsonify({"error": "Game not found"}), 404)

    review = next((r for r in game.get("reviews", []) if str(r["_id"]) == r_id), None)
    if not review:
        return make_response(jsonify({"error": "Review not found"}), 404)

    # Ownership or admin
    if not g.user["admin"] and review.get("user_id") != g.user["user_id"]:
        return make_response(jsonify({"error": "Not authorized to edit this review"}), 403)

    update_fields = {}

    if "comment" in data:
        update_fields["reviews.$.comment"] = data["comment"]

    if "rating" in data:
        try:
            rating = int(data["rating"])
            if rating < 1 or rating > 10:
                return make_response(jsonify({"error": "Rating must be between 1 and 10"}), 400)
            update_fields["reviews.$.rating"] = rating
        except ValueError:
            return make_response(jsonify({"error": "Rating must be a number"}), 400)

    if not update_fields:
        return make_response(jsonify({"error": "No valid fields provided"}), 400)

    games.update_one({"_id": ObjectId(g_id), "reviews._id": ObjectId(r_id)}, {"$set": update_fields})

    return make_response(jsonify({"message": "Review updated successfully"}), 200)





# --------------------------------------------------------------------------------
# DELETE REVIEW
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games/<string:g_id>/reviews/<string:r_id>", methods=["DELETE"])
@token_required
def delete_review(g_id, r_id):
    if not ObjectId.is_valid(g_id) or not ObjectId.is_valid(r_id):
        return make_response(jsonify({"error": "Invalid ID format"}), 400)

    game = games.find_one({"_id": ObjectId(g_id)}, {"reviews": 1})
    if not game:
        return make_response(jsonify({"error": "Game not found"}), 404)

    review = next((r for r in game.get("reviews", []) if str(r["_id"]) == r_id), None)

    if not review:
        return make_response(jsonify({"error": "Review not found"}), 404)

    # Ownership enforcement
    if not g.user["admin"] and review.get("user_id") != g.user["user_id"]:
        return make_response(jsonify({"error": "Not authorized to delete this review"}), 403)

    result = games.update_one(
        {"_id": ObjectId(g_id)},
        {"$pull": {"reviews": {"_id": ObjectId(r_id)}}}
    )

    if result.modified_count == 1:
        return make_response(jsonify({"message": "Review deleted successfully"}), 200)

    return make_response(jsonify({"error": "Delete failed"}), 500)



# --------------------------------------------------------------------------------
# GET AWARD LEADERBOARD
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games/award-leaderboard", methods=["GET"])
def get_award_leaderboard():

    # Pagination parameters and validation
    try:
        page_num = int(request.args.get("pn", 1))
        page_size = int(request.args.get("ps", 10))
        if page_num < 1 or page_size < 1:
            return make_response(jsonify({"error": "Page number and page size must be positive integers"}), 400)
    except ValueError:
        return make_response(jsonify({"error": "Page number and page size must be integers"}), 400)

    skip_amount = page_size * (page_num - 1)

    pipeline = [
        {"$unwind": "$awards"},
        {"$group": {
            "_id": {"id": "$_id", "title": "$title"},
            "award_count": {"$sum": 1}
        }},
        {"$sort": {"award_count": -1}},
        {"$skip": skip_amount},
        {"$limit": page_size},
        {"$project": {
            "_id": 0,
            "id": {"$toString": "$_id.id"},
            "title": "$_id.title",
            "award_count": 1
        }}
    ]

    results = list(games.aggregate(pipeline))
    return make_response(jsonify(results), 200)


# --------------------------------------------------------------------------------
# GET CLOSEST DEV HQ
# --------------------------------------------------------------------------------

from math import radians

@app.route("/api/v1.0/games/closest", methods=["GET"])
def closest_game_studio():
    try:
        lng = float(request.args.get("lng"))
        lat = float(request.args.get("lat"))
        radius = float(request.args.get("radius", 50000))  # meters
        limit = int(request.args.get("limit", 5))  # number of results to return
    except (TypeError, ValueError):
        return make_response(jsonify({"error": "Longitude, latitiude, radius, and limit must be numbers"}), 400)

    pipeline = [
        {
            "$geoNear": {
                "near": {
                    "type": "Point",
                    "coordinates": [lng, lat]
                },
                "distanceField": "distance",
                "spherical": True,
                "maxDistance": radius
            }
        },
        {
            "$project": {
                "_id": {"$toString": "$_id"},
                "title": 1,
                "developer": 1,
                "distance": 1
            }
        },
        { "$limit": limit }
    ]

    results = list(games.aggregate(pipeline))

    if len(results) > 0:
        for doc in results:
            doc["distance_km"] = round(doc["distance"] / 1000, 2)
            del doc["distance"]
        return make_response(jsonify({
            "message": "Nearest game studios",
            "count": len(results),
            "results": results
        }), 200)

    # Fallback: closest overall if none within radius
    fallback_pipeline = [
        {
            "$geoNear": {
                "near": {
                    "type": "Point",
                    "coordinates": [lng, lat]
                },
                "distanceField": "distance",
                "spherical": True
            }
        },
        {
            "$project": {
                "_id": {"$toString": "$_id"},
                "title": 1,
                "developer": 1,
                "distance": 1
            }
        },
        { "$limit": 1 }
    ]

    fallback = list(games.aggregate(fallback_pipeline))

    if len(fallback) > 0:
        closest = fallback[0]
        closest["distance_km"] = round(closest["distance"] / 1000, 2)
        del closest["distance"]
        return make_response(jsonify({
            "message": "No nearby developer headquarters found, showing the closest one instead",
            "result": closest
        }), 200)

    # No geospatial data in DB at all
    return make_response(jsonify({"error": "No games in database have developer location data"}), 404)





if __name__ == "__main__":
    app.run(debug=True)