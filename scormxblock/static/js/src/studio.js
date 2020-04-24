function ScormStudioXBlock(runtime, element) {

    var handlerUrl = runtime.handlerUrl(element, 'studio_submit');

    $(element).find('.save-button').bind('click', function() {
        var form_data = new FormData();
        var file_data = $(element).find('#scorm_file').prop('files')[0];
        var display_name = $(element).find('input[name=display_name]').val();
        var has_score = $(element).find('select[name=has_score]').val();
        var width = $(element).find('input[name=width]').val();
        var height = $(element).find('input[name=height]').val();

        form_data.append('file', file_data);
        form_data.append('display_name', display_name);
        form_data.append('has_score', has_score);
        form_data.append('width', width);
        form_data.append('height', height);
        runtime.notify('save', {
            state: 'start'
        });

        $.ajax({
            url: handlerUrl,
            dataType: 'json',
            cache: false,
            contentType: false,
            processData: false,
            data: form_data,
            type: "POST",
            success: function(response) {
                if (response.errors.length > 0) {
                    response.errors.forEach(function(error) {
                        runtime.notify("error", {
                            "message": error,
                            "title": "Scorm component save error"
                        });
                    });
                } else {
                    runtime.notify('save', {
                        state: 'end'
                    });
                }
            }
        });

    });

    $(element).find('.cancel-button').bind('click', function() {
        runtime.notify('cancel', {});
    });

}