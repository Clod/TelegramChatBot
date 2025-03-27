
```mermaid

sequenceDiagram                                                                                                           
    participant User                                                                                                      
    participant TelegramAPI                                                                                               
    participant FlaskWebhook as Flask App (app.py)                                                                        
    participant TelebotLib as Telebot (bot)                                                                               
    participant Handlers as Bot Handlers (app.py funcs)                                                                   
    participant DBFunctions as DB Utils (app.py funcs)                                                                    
    participant SQLiteDB as Database (bot_users.db)                                                                       
    participant GeminiAPI                                                                                                 
    participant FileSystem                                                                                                
                                                                                                                          
    %% User sends /start command %%                                                                                       
    User->>TelegramAPI: Send /start                                                                                       
    TelegramAPI->>FlaskWebhook: POST /<TOKEN> (Webhook Update)                                                            
    activate FlaskWebhook                                                                                                 
    FlaskWebhook->>TelebotLib: process_new_updates(update)                                                                
    activate TelebotLib                                                                                                   
    TelebotLib->>Handlers: call send_welcome(message)                                                                     
    activate Handlers                                                                                                     
    Handlers->>DBFunctions: save_user(user, chat_id)                                                                      
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: INSERT/UPDATE users                                                                           
    SQLiteDB-->>DBFunctions: OK                                                                                           
    deactivate DBFunctions                                                                                                
    Handlers->>DBFunctions: save_message(message)                                                                         
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: INSERT user_messages                                                                          
    SQLiteDB-->>DBFunctions: OK                                                                                           
    deactivate DBFunctions                                                                                                
    Handlers->>DBFunctions: log_interaction(user_id, 'command_start')                                                     
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: INSERT user_interactions                                                                      
    SQLiteDB-->>DBFunctions: OK                                                                                           
    deactivate DBFunctions                                                                                                
    Handlers->>DBFunctions: get_user_preferences(user_id)                                                                 
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: SELECT user_preferences                                                                       
    SQLiteDB-->>DBFunctions: Preferences Data                                                                             
    deactivate DBFunctions                                                                                                
    Handlers->>TelebotLib: bot.reply_to(message, text, markup)                                                            
    TelebotLib->>TelegramAPI: Send Welcome Message + Menu                                                                 
    TelegramAPI-->>User: Show Welcome Message + Menu                                                                      
    deactivate Handlers                                                                                                   
    deactivate TelebotLib                                                                                                 
    FlaskWebhook-->>TelegramAPI: 200 OK                                                                                   
    deactivate FlaskWebhook                                                                                               
                                                                                                                          
    %% User sends a Photo %%                                                                                              
    User->>TelegramAPI: Send Photo Message                                                                                
    TelegramAPI->>FlaskWebhook: POST /<TOKEN> (Webhook Update)                                                            
    activate FlaskWebhook                                                                                                 
    FlaskWebhook->>TelebotLib: process_new_updates(update)                                                                
    activate TelebotLib                                                                                                   
    TelebotLib->>Handlers: call handle_photo(message)                                                                     
    activate Handlers                                                                                                     
    Handlers->>DBFunctions: save_user(user, chat_id)                                                                      
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: INSERT/UPDATE users                                                                           
    SQLiteDB-->>DBFunctions: OK                                                                                           
    deactivate DBFunctions                                                                                                
    Handlers->>DBFunctions: save_message(message) %% Saves photo message info %%                                          
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: INSERT user_messages (type=photo)                                                             
    SQLiteDB-->>DBFunctions: OK                                                                                           
    deactivate DBFunctions                                                                                                
    Handlers->>DBFunctions: log_interaction(user_id, 'photo_message')                                                     
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: INSERT user_interactions                                                                      
    SQLiteDB-->>DBFunctions: OK                                                                                           
    deactivate DBFunctions                                                                                                
    Handlers->>TelebotLib: bot.reply_to(message, "Processing...")                                                         
    TelebotLib->>TelegramAPI: Send "Processing..." Message                                                                
    TelegramAPI-->>User: Show "Processing..."                                                                             
                                                                                                                          
    Note right of Handlers: download_image_from_telegram() starts                                                         
    Handlers->>TelebotLib: bot.get_file(file_id)                                                                          
    TelebotLib->>TelegramAPI: Get File Info Request                                                                       
    TelegramAPI-->>TelebotLib: File Info Response                                                                         
    Handlers->>TelebotLib: bot.download_file(file_path)                                                                   
    TelebotLib->>TelegramAPI: Download File Request                                                                       
    TelegramAPI-->>TelebotLib: File Bytes                                                                                 
    Handlers->>FileSystem: Save image to temp file                                                                        
    activate FileSystem                                                                                                   
    FileSystem-->>Handlers: Saved file path                                                                               
    deactivate FileSystem                                                                                                 
    Note right of Handlers: download_image_from_telegram() ends                                                           
                                                                                                                          
    Note right of Handlers: process_image_with_gemini() starts                                                            
    Handlers->>GeminiAPI: POST /generateContent (image data, auth)                                                        
    activate GeminiAPI                                                                                                    
    GeminiAPI-->>Handlers: Gemini Response (JSON)                                                                         
    deactivate GeminiAPI                                                                                                  
    Note right of Handlers: process_image_with_gemini() ends                                                              
                                                                                                                          
    Handlers->>Handlers: extract_text_from_gemini_response()                                                              
    Handlers->>Handlers: Convert extracted text to JSON (json_to_save)                                                    
                                                                                                                          
    Handlers->>DBFunctions: save_image_processing_result(..., json_to_save)                                               
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: INSERT image_processing_results                                                               
    SQLiteDB-->>DBFunctions: OK                                                                                           
    deactivate DBFunctions                                                                                                
                                                                                                                          
    Handlers->>DBFunctions: INSERT user_messages (processed text)                                                         
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: INSERT user_messages (type=processed_text_from_image)                                         
    SQLiteDB-->>DBFunctions: OK                                                                                           
    deactivate DBFunctions                                                                                                
                                                                                                                          
    Handlers->>TelebotLib: bot.edit_message_text(chat_id, msg_id, extracted_text)                                         
    TelebotLib->>TelegramAPI: Edit Message Request                                                                        
    TelegramAPI-->>User: Show Extracted Text                                                                              
                                                                                                                          
    Handlers->>DBFunctions: log_interaction(user_id, 'sent_extracted_text', data)                                         
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: INSERT user_interactions                                                                      
    SQLiteDB-->>DBFunctions: OK                                                                                           
    deactivate DBFunctions                                                                                                
                                                                                                                          
    Handlers->>FileSystem: cleanup_temp_file(image_path)                                                                  
    activate FileSystem                                                                                                   
    FileSystem->>FileSystem: Delete temp file                                                                             
    FileSystem-->>Handlers: OK                                                                                            
    deactivate FileSystem                                                                                                 
                                                                                                                          
    deactivate Handlers                                                                                                   
    deactivate TelebotLib                                                                                                 
    FlaskWebhook-->>TelegramAPI: 200 OK                                                                                   
    deactivate FlaskWebhook                                                                                               
                                                                                                                          
    %% User clicks an Inline Button (e.g., view_my_data) %%                                                               
    User->>TelegramAPI: Click Inline Button                                                                               
    TelegramAPI->>FlaskWebhook: POST /<TOKEN> (Webhook Update - CallbackQuery)                                            
    activate FlaskWebhook                                                                                                 
    FlaskWebhook->>TelebotLib: process_new_updates(update)                                                                
    activate TelebotLib                                                                                                   
    TelebotLib->>Handlers: call handle_callback_query(call)                                                               
    activate Handlers                                                                                                     
    Handlers->>DBFunctions: save_user(user, chat_id)                                                                      
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: INSERT/UPDATE users                                                                           
    SQLiteDB-->>DBFunctions: OK                                                                                           
    deactivate DBFunctions                                                                                                
    Handlers->>DBFunctions: log_interaction(user_id, 'button_click', call.data)                                           
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: INSERT user_interactions                                                                      
    SQLiteDB-->>DBFunctions: OK                                                                                           
    deactivate DBFunctions                                                                                                
                                                                                                                          
    alt call.data == "view_my_data"                                                                                       
        Handlers->>DBFunctions: get_user_data_summary(user_id)                                                            
        activate DBFunctions                                                                                              
        DBFunctions->>SQLiteDB: SELECT users, user_preferences, counts, messages                                          
        SQLiteDB-->>DBFunctions: Summary Data                                                                             
        deactivate DBFunctions                                                                                            
        Handlers->>TelebotLib: bot.edit_message_text(chat_id, msg_id, summary_text, markup)                               
        TelebotLib->>TelegramAPI: Edit Message Request                                                                    
        TelegramAPI-->>User: Show Data Summary                                                                            
    else call.data == "delete_my_data"                                                                                    
        Handlers->>TelebotLib: bot.edit_message_text(chat_id, msg_id, confirm_text, markup)                               
        TelebotLib->>TelegramAPI: Edit Message Request                                                                    
        TelegramAPI-->>User: Show Delete Confirmation                                                                     
    else call.data == "confirm_delete"                                                                                    
        Handlers->>DBFunctions: delete_user_data(user_id)                                                                 
        activate DBFunctions                                                                                              
        DBFunctions->>SQLiteDB: DELETE FROM multiple tables                                                               
        SQLiteDB-->>DBFunctions: Success/Fail                                                                             
        deactivate DBFunctions                                                                                            
        Handlers->>TelebotLib: bot.edit_message_text(chat_id, msg_id, result_text)                                        
        TelebotLib->>TelegramAPI: Edit Message Request                                                                    
        TelegramAPI-->>User: Show Deletion Result                                                                         
    else Other button clicks (menu navigation)                                                                            
        Handlers->>TelebotLib: bot.edit_message_text(chat_id, msg_id, new_menu_text, new_markup)                          
        TelebotLib->>TelegramAPI: Edit Message Request                                                                    
        TelegramAPI-->>User: Show New Menu/Submenu                                                                        
    end                                                                                                                   
                                                                                                                          
    deactivate Handlers                                                                                                   
    deactivate TelebotLib                                                                                                 
    FlaskWebhook-->>TelegramAPI: 200 OK                                                                                   
    deactivate FlaskWebhook                                                                                               
                                                                                                                          
    %% Admin accesses a Flask route (e.g., /db_users) %%                                                                  
    participant Admin                                                                                                     
    Admin->>FlaskWebhook: GET /db_users                                                                                   
    activate FlaskWebhook                                                                                                 
    FlaskWebhook->>DBFunctions: Query DB for users                                                                        
    activate DBFunctions                                                                                                  
    DBFunctions->>SQLiteDB: SELECT users, preferences, counts                                                             
    SQLiteDB-->>DBFunctions: User Data List                                                                               
    deactivate DBFunctions                                                                                                
    FlaskWebhook-->>Admin: Return JSON Response                                                                           
    deactivate FlaskWebhook                                                            
                                   