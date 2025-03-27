from flask import Flask                                                                                                              
                                                                                                                                    
app = Flask(__name__)                                                                                                                
                                                                                                                                    
@app.route('/')                                                                                                                      
def hello_world():                                                                                                                   
    return 'Hello, World! (SSL Test)'                                                                                                
                                                                                                                                    
if __name__ == '__main__':                                                                                                           
    app.run(host='0.0.0.0', port=443, ssl_context=('certs/fullchain.pem', 'certs/privkey.pem')) 