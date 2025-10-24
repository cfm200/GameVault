from flask import Flask, request, jsonify, make_response
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)

# MongoDB Connection
client = MongoClient("mongodb://127.0.0.1:27017")
db = client.gameDB
games = db.games

# --------------------------------------------------------------------------------
# GET ALL GAMES
# --------------------------------------------------------------------------------

@app.route("/api/v1.0/games", methods=["GET"])
def show_all_games():
    page_num, page_size = 1, 10
    if request.args.get('pn'):
        page_num = int(request.args.get('pn'))
    if request.args.get('ps'):
        page_size = int(request.args.get('ps'))
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

    # Validate ObjectId format before attempting to use it
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid Game ID format"}), 400)
    
    data_to_return = []
    
    # Find the game and retrieve only the reviews field
    game = games.find_one({"_id": ObjectId(id)}, {"reviews": 1, "_id": 0})
    
    # Check if game exists
    if not game:
        return make_response(jsonify({"error": "Invalid Game ID"}), 404)
    
    # Check if game has reviews
    if "reviews" not in game or len(game["reviews"]) == 0:
        return make_response(jsonify({"error": "No reviews found"}), 404)
    
    # Convert ObjectId to string for JSON serialization
    for review in game["reviews"]:
        if "_id" in review:
            review["_id"] = str(review["_id"])
        data_to_return.append(review)
    
    # Get pagination parameters from query string (default: page 1, 10 items per page)
    page_num = int(request.args.get("pn", 1))
    page_size = int(request.args.get("ps", 10))
    
    # Calculate the starting index for pagination
    page_start = (page_size * (page_num - 1))
    
    # Get the paginated subset of reviews
    paginated_reviews = data_to_return[page_start : page_start + page_size]
    
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


if __name__ == "__main__":
    app.run(debug=True)