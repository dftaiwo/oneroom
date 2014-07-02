//Extensions to the jQuery library
/*
 * Watch Enter Key 
 * http://stackoverflow.com/a/6524584
 */
$.fn.pressEnter = function(fn) {

        return this.each(function() {
                $(this).bind('enterPress', fn);
                $(this).keyup(function(e) {
                        if (e.keyCode == 13)
                        {
                                $(this).trigger("enterPress");
                        }
                })
});
}       