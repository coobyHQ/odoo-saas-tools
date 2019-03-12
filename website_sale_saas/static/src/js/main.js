odoo.define('saas_portal_portal.typedbname_extrainfo', function (require) {
    'use strict';

    var ajax = require('web.ajax');

$(document).ready(function() {

  var check_dbname = function($input) {
      var error = false;
      var db_name = $input.val().toLowerCase();
      if (!db_name) {
          $input.attr('data-content', "Please choose your domain name");
          error = true;
      }
      if (!error && (/\s/.test(db_name))) {
          $input.attr('data-content', "Spaces are not allowed in domain names");
          error = true;
      } else if (db_name.length < 4) {
          $input.attr('data-content', "Your domain must be at least 4 characters long");
          error = true;
        } else if(!(/^[a-zA-Z0-9]*$/i).test(db_name)) {
          $input.attr('data-content', "Domain name isn't valid");
          error = true;
      }

      if (error) {
          $input.popover('show');
      }
  };


  $('a.btn.btn-primary.pull-right.mb32.o_website_form_send').on('click', function(event) {
      event.preventDefault();
      var $self = $(this);
      var $db_input = $('input#dbname');
      check_dbname($db_input);
  });

  $('input#dbname').popover({
      html: true
  });
  $('input#dbname').on('keyup', function() {
      var $input = $(this);
      $input.popover('hide');
  });

});
});