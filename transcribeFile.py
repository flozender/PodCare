import io
import os

import speech_recognition as sr 
import os 
from pydub import AudioSegment
from pydub.silence import split_on_silence
from google.cloud import speech
# from google.cloud.speech import enums
# from google.cloud.speech import types
import wave
from google.cloud import storage

import requests

from flask import Flask, request, redirect, session, url_for, Response, json, render_template, send_from_directory
from werkzeug.utils import secure_filename
from flask.json import jsonify
from flask_cors import CORS


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config.from_object(__name__)
CORS(app)



def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



def getfile(url):
    r = requests.get(url, allow_redirects=True)
    open('download.mp3', 'wb').write(r.content)
    return ('download.mp3')


def trimfile(filein):
    startMin = 0
    startSec = 0

    endMin = 1
    endSec = 45

    # Time to miliseconds
    startTime = startMin*60*1000+startSec*1000
    endTime = endMin*60*1000+endSec*1000

    # Opening file and extracting segment
    song = AudioSegment.from_mp3( filein )
    extract = song[startTime:endTime]

    # Saving
    extract.export( 'extract.mp3', format="mp3")

    return 'extract.mp3'


def mp3_to_wav(audio_file_name):
    if audio_file_name.split('.')[1] == 'mp3':    
        sound = AudioSegment.from_mp3(audio_file_name)
        audio_file_name = audio_file_name.split('.')[0] + '.wav'
        sound.export(audio_file_name, format="wav")
        


def stereo_to_mono(audio_file_name):
    sound = AudioSegment.from_wav(audio_file_name)
    sound = sound.set_channels(1)
    sound.export(audio_file_name, format="wav")


def frame_rate_channel(audio_file_name):
    with wave.open(audio_file_name, "rb") as wave_file:
        frame_rate = wave_file.getframerate()
        channels = wave_file.getnchannels()
        return frame_rate,channels

    


# create a speech recognition object
r = sr.Recognizer()

# a function that splits the audio file into chunks
# and applies speech recognition
def get_large_audio_transcription(path):
    """
    Splitting the large audio file into chunks
    and apply speech recognition on each of these chunks
    """
    # open the audio file using pydub
    sound = AudioSegment.from_wav(path)  
    # split audio sound where silence is 700 miliseconds or more and get chunks
    chunks = split_on_silence(sound,
        # experiment with this value for your target audio file
        min_silence_len = 500,
        # adjust this per requirement
        silence_thresh = sound.dBFS-14,
        # keep the silence for 1 second, adjustable as well
        keep_silence=500,
    )
    folder_name = "audio-chunks"
    # create a directory to store the audio chunks
    if not os.path.isdir(folder_name):
        os.mkdir(folder_name)
    whole_text = ""
    # process each chunk 
    for i, audio_chunk in enumerate(chunks, start=1):
        # export audio chunk and save it in
        # the `folder_name` directory.
        chunk_filename = os.path.join(folder_name, f"chunk{i}.wav")
        audio_chunk.export(chunk_filename, format="wav")
        # recognize the chunk
        with sr.AudioFile(chunk_filename) as source:
            audio_listened = r.record(source)
            # try converting it to text
            try:
                text = r.recognize_google(audio_listened)
            except sr.UnknownValueError as e:
                print("Error:", str(e))
            else:
                text = f"{text.capitalize()}. "
                print(chunk_filename, ":", text)
                whole_text += text
    # return the text for all chunks detected
    return whole_text


def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)



def delete_blob(bucket_name, blob_name):
    """Deletes a blob from the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(blob_name)

    blob.delete()


def google_transcribe(audio_file_name):
    
    file_name = audio_file_name
    
    mp3_to_wav(file_name)

    audio_file_name = 'extract.wav'

    # The name of the audio file to transcribe

    print(file_name)
    
    frame_rate, channels = frame_rate_channel('extract.wav')
    
    if channels > 1:
        stereo_to_mono('extract.wav')
    
    bucket_name = 'callsaudiofilesx'
    source_file_name = audio_file_name
    destination_blob_name = audio_file_name
    
    upload_blob(bucket_name, source_file_name, destination_blob_name)
    
    gcs_uri = 'gs://callsaudiofilesx/' + audio_file_name
    transcript = ''
    
    client = speech.SpeechClient()
    audio = speech.RecognitionAudio(uri=gcs_uri)

    config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=frame_rate,
    language_code='en-US')

    # Detects speech in the audio file
    operation = client.long_running_recognize(config=config, audio=audio)
    response = operation.result(timeout=10000)

    for result in response.results:
        transcript += result.alternatives[0].transcript
    
    delete_blob(bucket_name, destination_blob_name)
    return transcript

##testing

# filename = 'test.mp3'

# filename = getfile('https://dcs.megaphone.fm/WSMM8548505894.mp3?key=0c22ff1274224c737f9aed1bc90c9ee9')


# efile = trimfile(filename)

# mp3_to_wav(efile)

# whole_text = ''
# stereo_to_mono('extract.wav')

#         # recognize the chunk
# with sr.AudioFile('extract.wav') as source:
#     audio_listened = r.record(source)
#     # try converting it to text
#     try:
#         text = r.recognize_google(audio_listened)
#     except sr.UnknownValueError as e:
#         print("Error:", str(e))
#     else:
#         text = f"{text.capitalize()}. "
#         # print(chunk_filename, ":", text)
#         whole_text += text


# whole_text = google_transcribe('extract.mp3')


# print (whole_text)

# print ('done')
##done testing

@app.route("/transcribe", methods=[ 'POST'])
def transcribereq():

    print(request)

    res = request.get_json()
    print (res)

    resraw = request.get_data()
    print (resraw)

    fileurl = res['url']

    filename = getfile(fileurl)

    efile = trimfile(filename)


    mp3_to_wav(efile)

    whole_text = ''

    whole_text = google_transcribe('extract.mp3')



    status = {}
    status["server"] = "up"
    status["transcript"] = whole_text
    status["request"] = res 

    statusjson = json.dumps(status)

    print(statusjson)

    js = "<html> <body>OK THIS WoRKS</body></html>"

    resp = Response(statusjson, status=200, mimetype='application/json')
    ##resp.headers['Link'] = 'http://google.com'

    return resp





@app.route("/file_upload", methods=["POST"])
def fileupload():

    if 'file' not in request.files:
          return "No file part"
    file = request.files['file']
    # if user does not select file, browser also
    # submit an empty part without filename
    if file.filename == '':
      return "No selected file"
    if file and allowed_file(file.filename):
        # UPLOAD_FOLDER = "./uploads"
        UPLOAD_FOLDER = "uploads"
  
        filename = secure_filename(file.filename)
        # file.save(os.path.join(UPLOAD_FOLDER, filename))
        file.save(filename)
        # uploadtogcp(os.path.join(UPLOAD_FOLDER, filename))
        uploadtogcp(os.path.join(filename))
        return 'https://storage.googleapis.com/hackybucket/current.jpg' 
    
    return 'file not uploaded successfully', 400


@app.route("/dummyJson", methods=['GET', 'POST'])
def dummyJson():

    print(request)

    res = request.get_json()
    print (res)

    resraw = request.get_data()
    print (resraw)

##    args = request.args
##    form = request.form
##    values = request.values

##    print (args)
##    print (form)
##    print (values)

##    sres = request.form.to_dict()
 

    status = {}
    status["server"] = "up"
    status["message"] = "some random message here"
    status["request"] = res 

    statusjson = json.dumps(status)

    print(statusjson)

    js = "<html> <body>OK THIS WoRKS</body></html>"

    resp = Response(statusjson, status=200, mimetype='application/json')
    ##resp.headers['Link'] = 'http://google.com'

    return resp




@app.route("/dummy", methods=['GET', 'POST'])
def dummy():

    ##res = request.json

    js = "<html> <body>OK THIS WoRKS</body></html>"

    resp = Response(js, status=200, mimetype='text/html')
    ##resp.headers['Link'] = 'http://google.com'

    return resp

@app.route("/api", methods=["GET"])
def index():
    if request.method == "GET":
        return {"hello": "world"}
    else:
        return {"error": 400}


if __name__ == "__main__":
    app.run(debug=True, host = 'localhost', port = 8003)
    # app.run(debug=True, host = '45.79.199.42', port = 8003)



