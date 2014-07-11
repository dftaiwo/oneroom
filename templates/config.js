/** This is an auto-generated file  **/
var chatServerUrl = '{{ chatServerUrl }}'
/*
var channelParams  = {
                channelToken:'{{ channelToken }}',
                channelId:'{{ channelId }}',
                clientSeq: '{{ client_seq }}',
                myNickname: '{{ myNickName }}',
                siteId:'{{ siteId }}'
}
*/
var orChatIframe = document.createElement('iframe');
orChatIframe.setAttribute('style'," width:300px; height:360px; overflow:hidden; position:fixed; bottom:0; right:20%; z-index:9;border:1px solid #999;");
orChatIframe.src = chatServerUrl+"widget?site_id={{ siteId }}";
orChatIframe.setAttribute('frameborder',"0");
orChatIframe.setAttribute('width',"100%");
orChatIframe.setAttribute('height',"100%");
document.body.appendChild(orChatIframe);
