function doGet(request) {
    try {
      // Authentication
      /*
      var apiKey = request.parameter.apiKey;
      var YOUR_API_KEY = "YOUR_GENERATED_API_KEY";
  
      if (apiKey !== YOUR_API_KEY) {
        return ContentService.createTextOutput("Unauthorized: Invalid API key").setMimeType(ContentService.MimeType.TEXT);
      }
      */
      // Get the ID
      var idToFind = request.parameter.id;
  
      if (!idToFind) {
          return ContentService.createTextOutput("Bad Request: Missing ID").setMimeType(ContentService.MimeType.TEXT);
      }
  
      // **Parse** the ID to ensure it's a number!  Crucial!
      idToFind = parseInt(idToFind, 10);  // Radix 10 for decimal
  
      if (isNaN(idToFind)) {
          return ContentService.createTextOutput("Bad Request: Invalid ID (not a number)").setMimeType(ContentService.MimeType.TEXT);
      }
  
      // Get the data
      var jsonOutput = getRowByIdAsJson(idToFind);
  
      // Handle the output
      if (jsonOutput) {
        return ContentService.createTextOutput(jsonOutput).setMimeType(ContentService.MimeType.JSON);
      } else {
        return ContentService.createTextOutput("Not Found: ID not found in the sheet").setMimeType(ContentService.MimeType.TEXT);
      }
  
    } catch (e) {
      // Log the error to the execution log
      Logger.log("Error in doGet: " + e);
      // Return an error message to the client
      return ContentService.createTextOutput("Error: " + e).setMimeType(ContentService.MimeType.TEXT);
    }
  }
  
  function getRowByIdAsJson(idToFind) {
    // Get the spreadsheet
    var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    Logger.log("Spreadsheet: " + spreadsheet.getName()); // Log the spreadsheet name
  
    // Get the first sheet (usually where the form responses are)
    var sheet = spreadsheet.getSheets()[0];
    Logger.log("Sheet: " + sheet.getName()); // Log the sheet name
  
    // Get the data range (all rows and columns with data)
    var range = sheet.getDataRange();
  
    // Get the values as a 2D array
    var values = range.getValues();
    Logger.log("Number of rows: " + values.length); // Log the number of rows
  
    // **"id" column is in column B, which is index 1**
    var idColumnIndex = 1;
    Logger.log("idColumnIndex: " + idColumnIndex); // Log the column index
  
    // Get the header row (first row) to use as keys in the JSON object
    var headers = values[0];
    Logger.log("Headers: " + headers); // Log the headers
  
    // Iterate through rows, starting from the *second* row (index 1) to skip the header.
    for (var i = 1; i < values.length; i++) {
      var row = values[i];
      Logger.log("Row " + i + ": " + row); // Log the entire row
  
      // Get the Id value from the current row
      var idValue = row[idColumnIndex];
      Logger.log("idValue (Row " + i + "): " + idValue + " (Type: " + typeof idValue + ")"); // Log the ID value and its type
      Logger.log("idToFind: " + idToFind + " (Type: " + typeof idToFind + ")");  //Log the idToFind and it's type
  
      // Compare the Id value with the value you're looking for
      if (idValue == idToFind) {
        // Found the matching row!
        Logger.log("MATCH FOUND for id " + idToFind + " in row " + i);
  
        // Create a JSON object (dictionary) from the row data
        var jsonObject = {};
        for (var j = 0; j < headers.length; j++) {
          jsonObject[headers[j]] = row[j];  // Key = header, Value = row value
        }
  
        Logger.log("JSON Object: " + JSON.stringify(jsonObject));
  
        return JSON.stringify(jsonObject); // Return the JSON string.
      }
    }
  
    // If the loop finishes without finding a match:
    Logger.log("No matching ID found.");
    return null;
  }
  
  // Example of how to call the function:
  function testGetRowByIdAsJson() {
    var idToSearchFor = 123456; // The ID from the spreadsheet.
  
    var foundJson = getRowByIdAsJson(idToSearchFor);
  
    if (foundJson) {
      // Parse the JSON string.
      var parsedJson = JSON.parse(foundJson);
  
      // Log the parsed JSON object to make sure it looks correct
      Logger.log(JSON.stringify(parsedJson, null, 2)); // Pretty-print the JSON
  
      // Example of how to access a specific value:
      Logger.log("Full Name: " + parsedJson["Full Name"]);
    } else {
      Logger.log("Row with ID " + idToSearchFor + " was not found.");
    }
  }