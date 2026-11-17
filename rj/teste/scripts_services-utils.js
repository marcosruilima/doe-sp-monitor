    
    function CallService(myUrl, myclass)
    { 
        //var myClass;
        //myClass = myclass;
        $.ajax({
            url: myUrl, 
            type: "GET",
            dataType: "html", 
            /*data: soapMessage, */
            contentType: "text/html; charset=\"utf-8\"",
            success: function(data, status){
                try {
                    var doc = data;
                    //alert(data.responseXML);
                    //alert(doc);
                    $(myclass).html(doc);
                    //alert(status + " dados" + data);
                }
                catch(ex) { alert(ex);}
            }, 
            error: function(request, status, error) { alert('error ' + error);}
        });

        return false;
    }

