# Gevent needed for sockets
from gevent import monkey
monkey.patch_all()

# Imports
import os
from flask import Flask, render_template, request, json
# from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
# import filters
import time
import pickle
import numpy as np
import json
import pickle
from sklearn.preprocessing import normalize
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse.linalg import svds
from sklearn.metrics.pairwise import cosine_similarity

start_time = time.time()
# Configure app
socketio = SocketIO()
app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])

net_id1 = "Judy Chen (jc2528)"
net_id2 = "Meghan Chen (mc2254)"
net_id3 = "Paula Moya Nieto (pm445)"
net_id4 = "Gabriel Winbush (gw262)"

with open('Data/FINAL_snacks_data.pickle', 'rb') as f:
	all_data = pickle.load(f)

with open('Data/index_to_title.pickle', 'rb') as f:
	index_to_title = pickle.load(f)

with open("Data/title_to_index.pickle", "rb") as f:
	title_to_index = pickle.load(f)

with open("Data/titles_to_asin.pickle", "rb") as f:
	titles_to_asin = pickle.load(f)

#REMOVING WEIRD ENTRIES
with open("Data/percentagesDict.pickle","rb") as f:
	percentagesDict = pickle.load(f);

with open('Data/docs_compressed.pickle', 'rb') as f:
	docs_compressed = pickle.load(f)

with open("Data/imagesDict.pickle","rb") as f:
	imagesDict = pickle.load(f);


# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

# DB
# db = SQLAlchemy(app)

# Import + Register Blueprints
# from app.accounts import accounts as accounts
# app.register_blueprint(accounts)
# from app.irsystem import irsystem as irsystem
# app.register_blueprint(irsystem)

# Initialize app w/SocketIO
socketio.init_app(app)

# HTTP error handling
@app.errorhandler(404)
def not_found(error):
  return render_template("404.html"), 404

@app.route("/")
def index():
	return render_template('index.html', net_id1=net_id1, net_id2=net_id2, net_id3=net_id3, net_id4=net_id4)

@app.route('/filterLevels', methods=['POST'])
def filterLevels():
	fat =  request.form.get('fat');
	carb = request.form.get('carb');
	protein = request.form.get('protein');
	similarSnacks = request.form.get('similarSnacks');
	dumps = json.dumps({'status':'OK','fat':fat,'carb':carb,'protein':protein, 'similarSnacks':similarSnacks});
	return dumps;

@app.route('/filters', methods=['POST'])
def filters():
	fatLevel = request.form.get('fat');
	carbLevel = request.form.get('carb');
	proteinLevel = request.form.get('protein');
	query_snack = request.form.get('similarSnacks');

	filtered_snacks = {}
	for product, d in percentagesDict.items():
		fat = d["fat"]
		carb = d["carb"]
		protein = d["protein"]
		fat_bool = False
		carb_bool = False
		protein_bool = False

		if (fatLevel == "Low" and fat > 0.0 and fat < 0.3) or (fatLevel == "Medium" and fat >= 0.3 and fat < 0.6) or (fatLevel == "High" and fat >= 0.6) or (fatLevel == "None"):
			fat_bool = True
		if (carbLevel == "Low" and carb > 0.0 and carb < 0.1) or (carbLevel == "Medium" and carb >= 0.1 and carb < 0.2) or (carbLevel == "High" and carb >= 0.2) or (carbLevel == "None"):
			carb_bool = True
		if (proteinLevel == "Low" and protein > 0.0 and protein < 0.2) or (proteinLevel == "Medium" and protein >= 0.2 and protein < 0.4) or (proteinLevel == "High" and protein >= 0.4) or (proteinLevel == "None"):
			protein_bool = True
		filtered_snacks[product] = (carb_bool, protein_bool, fat_bool)

	#START RANKING STUFF
	w1 = 0.05 #does occur
	w2 = 0.05 #rating
	w3 = 0.3 #svd score
	w4 = 0.2 #matches carb
	w5 = 0.2 #matches protein
	w6 = 0.2 #matches fat

	# FIND SIM SNACK IF QUERY NOT IN DATABASE
	if query_snack not in list(all_data.keys()):
		all_titles = list(all_data.keys())
		all_titles.insert(0, query_snack)
		vectorizer=TfidfVectorizer()
		matrix=vectorizer.fit_transform(all_titles)
		cs=cosine_similarity(matrix[0], matrix)
		sorted_row = np.argsort(cs, axis=1)[0][::-1]
		query_snack = all_titles[sorted_row[1]]
	print('NEW QUERY : ' + query_snack)

	# SVD
	snack_index_in = title_to_index[query_snack]

	sims = docs_compressed.dot(docs_compressed[snack_index_in,:])
	asort = np.argsort(-sims)
	svd_sorted = [(index_to_title[i],sims[i]/sims[asort[0]]) for i in asort[1:]]
	svd_sorted.append((query_snack, 1.0))

	#Return sorted list of sim scores
	# scores_lst = []
	scores = np.zeros((len(svd_sorted),1))
	for i in range(len(svd_sorted)):
		snack, svd_score = svd_sorted[i]
		does_cooccur = snack in all_data[query_snack]['also_bought']
		rating = all_data[snack]['rating']
		carb, protein, fat = filtered_snacks[snack]
		score = w1*does_cooccur + w2*rating + w3*svd_score + w4*carb + w5*protein + w6*fat
		scores[i] = score
	# print(scores)
	# scores = normalize(scores, axis = 1)
	# scores = scores.astype(int)
	# print(scores[20:])

	scores_lst = []
	for j in range(len(svd_sorted)):
		snack, _ = svd_sorted[j]
		scores_lst.append((snack, round(float(scores[j,:]),2)))
	scores_lst.sort(key=lambda tup: tup[1], reverse=True)

	base_url = 'https://amazon.com/dp/'
	scored_filtered_lst = [(snack_name, percentagesDict[snack_name], base_url + titles_to_asin[snack_name], snack_score, imagesDict[snack_name]) for (snack_name, snack_score) in scores_lst]

	return json.dumps(scored_filtered_lst)

end_time = time.time()
time_elapsed = end_time - start_time
print("Time Elapsed:", time_elapsed, "seconds")
