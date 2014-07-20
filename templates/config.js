/** This is an auto-generated file that should not be cached **/
var chatServerUrl = '{{ chatServerUrl }}'
if(typeof(chatWindowCount)=='undefined'){
        var chatWindowCount = 0;
}else{
        chatWindowCount++;
}
var orChatIframe = document.createElement('iframe');
orChatIframe.setAttribute('style'," width:300px; height:400px; overflow:hidden; position:fixed; bottom:0; right:12%; z-index:9;border:1px solid #999;");
//orChatIframe.setAttribute('style'," width:300px; height:400px; overflow:hidden; bottom:0; right:12%; z-index:9;border:1px solid #999;");
orChatIframe.src = chatServerUrl+"widget?site_id={{ siteId }}";
orChatIframe.setAttribute('frameborder',"0");
orChatIframe.setAttribute('width',"100%");
orChatIframe.setAttribute('height',"100%");
document.body.appendChild(orChatIframe);

