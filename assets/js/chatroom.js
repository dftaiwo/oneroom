var debugMode = true;
var outgoingMessages = {};
var myNickname = '-Me-';
var myMsgNickname = 'Me';//What is displayed in my chat for me
var plusAuthCompleted = false;
var isConnected = false;
var authenticatedUser = false;
if (typeof (console) == "undefined") {
        window.console = {
                log: function() {
                        //nothing to do then...Sad :(
                }
        };
}
var message_handlers = {
        'echo': handleDirectPrint,
        'clientsList': handleClientList,
        'newMessage': handleNewMessage,
        'refreshCall': handleRefreshCall,
}

var connected = false,
        clientSequence = 0,
        clientSequences = [];
var channel;
var autoConnect = true;
var globalChannelParams = {};


function setChannelParams(channelParams) {
        logMessage("Setting channel Params", channelParams);
        globalChannelParams = channelParams;
        if (channelParams.myNickname) {
                myNickname = channelParams.myNickname;
        }
}
function getChannelParams() {
        return globalChannelParams;

}
function connectChannel() {
        channelParams = getChannelParams();
//        logMessage('Channel Params', channelParams);

        channel = new goog.appengine.Channel(channelParams.channelToken);
        logMessage("Connecting to server...");
        channel.open({
                onopen: function() {
                        connected = true;
                        logMessage("===============================================");
                        logMessage("Connected to [" + getChannelId() + "]");
                        setConnectionStatus(true);
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
                        logMessage("Disconnected from [" + getChannelId() + "]");
                        setConnectionStatus(false);

                        logMessage("===============================================");
                        //Should I refresh?
                        if (autoConnect)
                                reconnectChannel();
                }
        });
}

function handleDirectPrint(msg) {
        logMessage(msg);
}
function updateClientsList(data) {
        var totalClients = data.totalClients;
        $('#totalClients').html(totalClients + ' Users');
}
function handleNewMessage(data) {

        updateClientsList(data);
        console.log(data);
        if (data.client_seq == getClientSeq() && data.channel_id == getChannelId()) {//because I sent this message
                logMessage('Message has gone around the world!');
                return;
        }
        addMessageToChat(data);
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
        updateClientsList(msg);
}

function logMessage(msg, msg2) {
        if (typeof (msg2) == 'undefined') {
                msg2 = '';

        }
        console.log(msg, msg2);
}



$('#textMessage').pressEnter(function() {
        if (!isConnected) {
                //showMessage("Disconnected. Click Ok to reconnect");
                reconnectChannel();
                return;
        }
        var messageToSend = $('#textMessage').val();
        messageToSend = messageToSend.trim();
        if (!messageToSend) {
                return;
        }
        $('#textMessage').val("");
        var msgTimeStamp = getTimestamp();
        var messageData = {
                msg: messageToSend,
                sender: authenticatedUser,
                site_id: getSiteId(),
        }
        addMessageToChat(messageData, msgTimeStamp,'Me');
        sendToServer(messageToSend, msgTimeStamp);

});

function addMessageToChat(messageData, msgTimeStamp,forcedSender) {


        var htmlToView = [];
        var message = messageData.msg;
        if (typeof (msgTimeStamp) == 'undefined') {
                htmlToView.push('<li>');
                playChatSound();
        } else {//This came from me
                htmlToView.push('<li class="pending" id="msg' + msgTimeStamp + '">');
        }
        if(typeof(messageData.sender.image)=='undefined'){
                htmlToView.push('<img src="/assets/img/avatar-02.svg" align="left" />');
        }else{
                htmlToView.push('<img src="'+messageData.sender.image+'" align="left" />');
        }
        htmlToView.push('<author>');
        if(typeof(forcedSender)=='undefined'){
                htmlToView.push(messageData.sender.name);
        }else{
                htmlToView.push(forcedSender);
        }
        htmlToView.push('</author>');
        htmlToView.push(message);
        
        htmlToView.push('<span></span>');
        htmlToView.push('</li>');

        $('#chatBoxList').append(htmlToView.join("\n"));

        //http://stackoverflow.com/a/3742972
        var $chatBoxContainer = $('#chatBox');
        var height = $chatBoxContainer[0].scrollHeight;
        //$chatBoxContainer.scrollTop(height);//1E10?
        $chatBoxContainer.animate({"scrollTop": height}, "slow");

}

function playChatSound() {
        $('#audioStreams')[0].play();
}

function sendToServer(messageToSend, msgTimeStamp) {
//        outgoingMessages.append(messageToSend);

        var requestParams = {
                channel_id: getChannelId(),
                client_seq: getClientSeq(),
                timestamp: msgTimeStamp,
                site_id: getSiteId(),
                msg: messageToSend
        }

        logMessage(requestParams);
        $.ajax({
                url: "/message",
                type: "POST",
                data: requestParams,
                dataType: 'json',
                success: function(data, textStatus, jqXHR)
                {
                        //logMessage(data);
                        window.setTimeout(function() {
                                $('#msg' + msgTimeStamp).removeClass('pending');
                        }, 500);
                },
                error: function(jqXHR, textStatus, errorThrown) {
                        logMessage(errorThrown, textStatus);
                }
        });
}

function getTimestamp() {
        return Math.floor(+new Date() / 1000);
}


function reconnectChannel() {
        if (!authenticatedUser) {
                logMessage('authenticatedUser', ' is false, so we will not connect');
                return;
        }
        //needs to get a fresh token, then connect
        logMessage("Trying to reconnect to Server");
        var requestParams = {
                site_id: siteIdentifier,
                user_id: authenticatedUser.id,
                name: authenticatedUser.name,
                image: authenticatedUser.image,
        }

        $.ajax({
                url: "/refreshToken",
                type: "POST",
                data: requestParams,
                dataType: 'json',
                success: function(data, textStatus, jqXHR)
                {
                        logMessage(data);
                        channelParams = {
                                channelToken: data.result.token,
                                channelId: data.result.channel_id,
                                clientSeq: data.result.client_seq,
                                siteId: data.result.site_id
                        }
                        siteIdentifier = data.result.site_id;
                        setChannelParams(channelParams);
                        connectChannel();
                        return;
                },
                error: function(jqXHR, textStatus, errorThrown) {
                        logMessage(errorThrown, textStatus);
                        logMessage("Waiting before trying again");
                        window.setTimeout(function() {
                                reconnectChannel();
                        }, 2500);
                }
        });

}

function getChannelId() {
        channelParams = getChannelParams();
        return channelParams.channelId;
}
function getClientSeq() {
        channelParams = getChannelParams();
        return channelParams.clientSeq;
}
function getSiteId() {
        channelParams = getChannelParams();
        return channelParams.siteId;
}

function setConnectionStatus(status) {
        isConnected = status;
}

function showMessage(msg) {
        alert(msg);
}

function loadGoogleApi() {
        gapi.client.load('plus', 'v1', getUserInfo);
        console.log('lading');
}

function signinCallback(authResult) {
        console.log(authResult);
        if (authResult['status']['signed_in']) {

                $('#signInBox').hide();

                $('#chatBox').show();

                plusAuthCompleted = true;

        } else {
                // Update the app to reflect a signed out user
                // Possible error values:
                //   "user_signed_out" - User is signed-out
                //   "access_denied" - User denied access to your app
                //   "immediate_failed" - Could not automatically log in the user
                console.log('Sign-in state: ' + authResult['error']);
                switch(authResult['error']){
                        case 'access_denied':
                                showMessage("We had a little difficulty signing you in. Please click on 'Sign-In' to try again");
                                break;
                        case 'immediate_failed':
                        default:

                }
                
        }
}


function getUserInfo() {
        if (!plusAuthCompleted) {
                window.setTimeout(
                        function() {
                                getUserInfo()
                        }
                , 500);
                return;

        }
        gapi.client.plus.people.get({userId: 'me'}).execute(handleUserInfo);
}

function handleUserInfo(userInfo) {
        if(!userInfo) return;
        var htmlToView = [];
        htmlToView.push('<li>');
        htmlToView.push('Welcome, ');
        htmlToView.push(userInfo.displayName);
        htmlToView.push('! <br /><br />');
        htmlToView.push('You are in this chat room.');
        htmlToView.push('</li>');
        $('#chatBoxList').append(htmlToView.join("\n"));
        
        console.log(authenticatedUser);
        authenticatedUser = {
                name: userInfo.displayName,
                id: userInfo.id,
                image: userInfo.image.url
        }

        myNickname = authenticatedUser.name;

        reconnectChannel();

}
