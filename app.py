from flask import Flask, request, jsonify, make_response
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import certifi
import os

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Connect to MongoDB Atlas
uri = os.getenv("MONGODB_URI")
client = MongoClient(uri, tlsCAFile=certifi.where())
db = client.GameVaultDB
games = db.games



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
def add_new_game():
    # Check if required fields are present
    if 'title' in request.form and \
        'platforms' in request.form and \
        'release_year' in request.form and \
        'developer' in request.form and \
        'publisher' in request.form and \
        'esrb' in request.form and \
        'genres' in request.form and \
        'modes' in request.form:

        # Check if title already exists
        title = request.form['title']
        existing_game = games.find_one({'title' : title})

        if existing_game:
            return make_response(jsonify({'error' : 'A game already exists with that title'}), 409)
        
        new_game = {
            'title' : request.form['title'],
            'platforms' : request.form.getlist('platforms'),
            'release_year' : request.form['release_year'],
            'developer' : request.form['developer'],
            'publisher' : request.form['publisher'],
            'esrb' : request.form['esrb'],
            'genres' : request.form.getlist('genres'),
            'modes' : request.form.getlist('modes'),
            'reviews' : []

        }

        # Add new game to collection
        new_game_id = games.insert_one(new_game)
        
        # Return link for newly created game
        new_game_link = "http://localhost:5000/api/v1.0/games/" + str(new_game_id.inserted_id)
        return make_response(jsonify({'url':new_game_link}), 201)
    else:
        return make_response(jsonify({'error':'Missing form data'}), 404)



# --------------------------------------------------------------------------------
# EDIT GAME
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games/<string:id>", methods=["PUT"])
def edit_game(id):

    # Validate ObjectId format
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid Game ID format"}), 400)

    # Define all expected fields
    expected_fields = ['title', 'platforms', 'release_year', 'developer', 'publisher', 'esrb', 'genres', 'modes']
    
    # Check if at least one field is present
    if not any(field in request.form for field in expected_fields):
        return make_response(jsonify({"error": "No valid fields provided"}), 400)
    
    # Build update dictionary dynamically
    update_data = {}
    
    # Handle list fields (using getlist)
    list_fields = ['platforms', 'genres', 'modes']
    for field in list_fields:
        if field in request.form:
            update_data[field] = request.form.getlist(field)
    
    # Handle regular string fields
    string_fields = ['title', 'release_year', 'developer', 'publisher', 'esrb']
    for field in string_fields:
        if field in request.form:
            update_data[field] = request.form[field]
    
    # Perform the update
    result = games.update_one({"_id": ObjectId(id)}, {"$set": update_data})
    
    if result.matched_count == 1:
        edited_game_link = "http://localhost:5000/api/v1.0/games/" + id
        return make_response(jsonify({"url": edited_game_link}), 200)
    else:
        return make_response(jsonify({"error": "Invalid Game ID"}), 404)



# --------------------------------------------------------------------------------
# DELETE GAME
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games/<string:id>", methods=["DELETE"])
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

@app.route("/api/v1.0/games/<string:id>/reviews", methods=["POST"])
def add_new_review(id):

    # Validate ObjectId format before attempting to use it
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid Game ID format"}), 400)
    
    # Check if all required fields are present in the form data
    if "username" in request.form and "comment" in request.form and "rating" in request.form:
        # Validate rating is between 1 and 10
        try:
            rating = int(request.form["rating"])
            if rating < 1 or rating > 10:
                return make_response(jsonify({"error": "Rating must be between 1 and 10"}), 400)
        except ValueError:
            return make_response(jsonify({"error": "Rating must be a valid number"}), 400)
        
        # Create new review object with a unique ID
        new_review = {
            "_id": ObjectId(),
            "username": request.form["username"],
            "comment": request.form["comment"],
            "rating": rating  # Use the validated integer value
        }
        
        # Push the new review to the game's reviews array
        result = games.update_one({"_id": ObjectId(id)}, {"$push": {"reviews": new_review}})
        
        # Check if a game was found and updated
        if result.matched_count == 1:
            # Build URL for the newly created review
            new_review_link = "http://localhost:5000/api/v1.0/games/" + id + "/reviews/" + str(new_review["_id"])
            return make_response(jsonify({"url": new_review_link}), 201)
        else:
            # Game ID was valid format but doesn't exist in database
            return make_response(jsonify({"error": "Invalid Game ID"}), 404)
    else:
        # Required form fields are missing
        return make_response(jsonify({"error": "Missing form data"}), 400)



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
def edit_review(g_id, r_id):

    # Validate game ID format
    if not ObjectId.is_valid(g_id):
        return make_response(jsonify({"error": "Invalid Game ID format"}), 400)
    
    # Validate review ID format
    if not ObjectId.is_valid(r_id):
        return make_response(jsonify({"error": "Invalid Review ID format"}), 400)
    
    # Check if at least one field is provided
    if "username" not in request.form and "comment" not in request.form and "rating" not in request.form:
        return make_response(jsonify({"error": "No valid fields provided"}), 400)
    
    try:
        # First check if the game exists
        game = games.find_one({"_id": ObjectId(g_id)}, {"reviews": 1, "_id": 0})
        
        if game is None:
            return make_response(jsonify({"error": "Invalid Game ID"}), 404)
        
        # Check if review exists in the game
        review_exists = any(str(r["_id"]) == r_id for r in game.get("reviews", []))
        
        if not review_exists:
            return make_response(jsonify({"error": "Invalid Review ID"}), 404)
        
        # Build the update dictionary dynamically
        edited_review = {}
        
        if "username" in request.form:
            edited_review["reviews.$.username"] = request.form["username"]
        
        if "comment" in request.form:
            edited_review["reviews.$.comment"] = request.form["comment"]
        
        if "rating" in request.form:
            # Validate rating is between 1 and 10
            try:
                rating = int(request.form["rating"])
                if rating < 1 or rating > 10:
                    return make_response(jsonify({"error": "Rating must be between 1 and 10"}), 400)
                edited_review["reviews.$.rating"] = rating
            except ValueError:
                return make_response(jsonify({"error": "Rating must be a valid number"}), 400)
        
        # Update the review
        result = games.update_one({"reviews._id": ObjectId(r_id)}, {"$set": edited_review})
        
        if result.modified_count == 1:
            edit_review_url = "http://localhost:5000/api/v1.0/games/" + g_id + "/reviews/" + r_id
            return make_response(jsonify({"url": edit_review_url}), 200)
        else:
            # This shouldn't happen since we already validated, but just in case
            return make_response(jsonify({"error": "Review update failed"}), 500)
    
    except Exception as e:
        # Handle any unexpected runtime errors
        return make_response(jsonify({"error": f"Server error: {str(e)}"}), 500)



# --------------------------------------------------------------------------------
# DELETE REVIEW
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games/<string:g_id>/reviews/<string:r_id>", methods=["DELETE"])
def delete_review(g_id, r_id):

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
        
        # Check if review exists in the game
        review_exists = any(str(r["_id"]) == r_id for r in game.get("reviews", []))
        
        if not review_exists:
            return make_response(jsonify({"error": "Invalid Review ID"}), 404)
        
        # Delete the review
        result = games.update_one(
            {"_id": ObjectId(g_id)}, 
            {"$pull": {"reviews": {"_id": ObjectId(r_id)}}}
        )
        
        if result.modified_count == 1:
            return make_response(jsonify({}), 204)
        else:
            # This shouldn't happen since we already validated, but just in case
            return make_response(jsonify({"error": "Review deletion failed"}), 500)
    
    except Exception as e:
        # Handle any unexpected runtime errors
        return make_response(jsonify({"error": f"Server error: {str(e)}"}), 500)



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
        return make_response(jsonify({"error": "lng, lat, radius, and limit must be numbers"}), 400)

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