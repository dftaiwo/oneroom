var debugMode = true;
var outgoingMessages = {};

if (typeof (console) == "undefined") {
        window.console = {
                log: function() {
                        //nothing to do then...Sad :(
                }
        };
}
var message_handlers = {
        'echo': handleDirectPrint,
        'client_list': handleClientList,
        'newMessage': handleNewMessage,
        'refreshCall': handleRefreshCall,
}
var connected = false,
        clientSequence = 0,
        clientSequences = [];

$().ready(function() {
        var channel = new goog.appengine.Channel(channelToken);
        logMessage("Connecting to server...");
        channel.open({
                onopen: function() {
                        connected = true;
                        logMessage("===============================================");
                        logMessage("Connected to [" + channelId + "]");
                },
                onmessage: function(msg) {
                        var data = jQuery.parseJSON(msg.data),
                                handler;
                        if (data !== undefined) {
                                handler = message_handlers[data.type];
                                if (handler !== undefined) {
                                        handler(data);
                                } else {
                                        logMessage("unhandled message type: " + data.type);
                                }
                        } else {
                                logMessage("ignoring malformed message: " + msg);
                        }
                },
                onerror: function(err) {
                        logMessage("error (" + err.code + ": " + err.description);
                },
                onclose: function() {
                        connected = false;
                        logMessage("Disconnected from [" + channelId + "]");
                        logMessage("===============================================");
                        //Should I refresh?
                }
        });

});

function handleDirectPrint(msg) {
        logMessage(msg);
}
function handleNewMessage(data) {
        var totalClients = data.totalClients;
        $('#totalClients').html(totalClients+' Users');
        if(data.clientSeq==clientSeq) {//because I sent this message
                logMessage('Message has gone around the world!');
                return;
        }
        addMessageToChat(data.msg);
}
;
function handleRefreshCall(data) {
        location.reload();
}
function handleClientList(msg) {
        if (!debugMode)
                return;
        var i,
                str = "";
        for (i = 0; i < msg.clients.length; i += 1) {
                if (i > 0) {
                        str += ", ";
                }
                str += msg.clients[i];
        }
//                                element.innerHTML = str;
        logMessage("RECV client_list [" + str + "]");
}

function logMessage(msg, msg2) {
        if (typeof (msg2) == 'undefined') {
                console.log(msg);
                return;
        }
        console.log(msg, msg2);
}



$('#textMessage').pressEnter(function() {

        var messageToSend = $('#textMessage').val();
        messageToSend = messageToSend.trim();
        if (!messageToSend) {
                return;
        }
        $('#textMessage').val("");
        addMessageToChat(messageToSend);
        sendToServer(messageToSend);

});

function addMessageToChat(message) {
        var htmlToView = [];
        htmlToView.push('<li>');
        htmlToView.push('<img src="/assets/img/avatar-02.svg" align="left" />');
        htmlToView.push(message);
        htmlToView.push('</li>');

        $('#chatBoxList').append(htmlToView.join("\n"));

        //http://stackoverflow.com/a/3742972
        var $chatBoxContainer = $('#chatBox');
        var height = $chatBoxContainer[0].scrollHeight;
        //$chatBoxContainer.scrollTop(height);//1E10?
        $chatBoxContainer.animate({"scrollTop": height}, "slow");

}

function sendToServer(messageToSend) {
//        outgoingMessages.append(messageToSend);
        var requestParams = {
                channel_id: channelId,
                client_seq: clientSeq,
                timestamp: getTimestamp(),
                msg: messageToSend
        }

        console.log(requestParams);
        $.ajax({
                url: "/message",
                type: "POST",
                data: requestParams,
                dataType: 'json',
                success: function(data, textStatus, jqXHR)
                {
                        console.log(data);
                },
                error: function(jqXHR, textStatus, errorThrown)
                {
                        console.log(errorThrown,textStatus);
                }
        });
}

function getTimestamp(){
        return Math.floor(+new Date()/1000);       
}
