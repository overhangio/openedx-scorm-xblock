function ScormStudioXBlock(runtime, element) {

    var handlerUrl = runtime.handlerUrl(element, 'studio_submit');
    var trans = window.gettext || function (text) { return text; };

    var $status = $(element).find('.scorm-upload-status');
    var $progress = $status.find('.scorm-upload-progress');
    var $message = $status.find('.scorm-upload-message');

    function showStatus(message, percent) {
        $message.text(message);
        if (percent === null || percent === undefined) {
            $status.addClass('scorm-upload-indeterminate');
        } else {
            $status.removeClass('scorm-upload-indeterminate');
            $progress.attr('value', percent);
        }
        $status.show();
    }

    function hideStatus() {
        $status.hide();
        $status.removeClass('scorm-upload-indeterminate');
        $progress.attr('value', 0);
        $message.text('');
    }

    // The runtime only hides its "Saving" notification on a save/end event, which would
    // also close the editor and refresh the block. Dismiss it directly so that a failed
    // upload can leave the editor open. runtime.notification is not a documented API.
    function dismissSavingIndicator() {
        try {
            if (runtime.notification && typeof runtime.notification.hide === 'function') {
                runtime.notification.hide();
            }
        } catch (e) {
            console.log('SCORM: could not dismiss the saving indicator', e);
        }
    }

    function notifyError(title, message) {
        runtime.notify('error', {
            title: title,
            message: message
        });
    }

    // A dropped connection or gateway error means the request outlived the web server
    // request timeout while the package was still being extracted. Extraction runs to
    // completion server-side, so this must not be reported as a lost upload.
    function describeFailure(jqXHR, textStatus) {
        var dropped = jqXHR.status === 0
            || jqXHR.status === 502
            || jqXHR.status === 504
            || textStatus === 'timeout';

        if (dropped) {
            return {
                stillProcessing: true,
                title: trans('SCORM upload still processing'),
                message: trans(
                    'The package was uploaded, but the server is still extracting it. '
                    + 'Large packages can take several minutes. Close this editor and reload '
                    + 'the page in a few minutes to see the result. If this happens with every '
                    + 'large package, ask your administrator to raise the request timeout of '
                    + 'the web server.'
                )
            };
        }

        var message = jqXHR.statusText || textStatus || trans('Unknown error');
        var contentType = jqXHR.getResponseHeader('content-type');
        if (contentType && contentType.indexOf('json') > -1 && jqXHR.responseText) {
            try {
                var parsed = JSON.parse(jqXHR.responseText);
                message = parsed.error || parsed.message || message;
            } catch (e) {
                // Fall back to the status-based message.
            }
        }
        return {
            stillProcessing: false,
            title: trans('Scorm component save error'),
            message: message
        };
    }

    $(element).find('.save-button').bind('click', function () {
        var $saveButton = $(this);
        var form_data = new FormData();
        var file_data = $(element).find('#scorm_file').prop('files')[0];
        var display_name = $(element).find('input[name=display_name]').val();
        var has_score = $(element).find('select[name=has_score]').val();
        var enable_navigation_menu = $(element).find('select[name=enable_navigation_menu]').val();
        var enable_fullscreen_button = $(element).find('select[name=enable_fullscreen_button]').val();
        var weight = $(element).find('input[name=weight]').val();
        var width = $(element).find('input[name=width]').val();
        var height = $(element).find('input[name=height]').val();
        var navigation_menu_width = $(element).find('input[name=navigation_menu_width]').val();
        var popup_on_launch = $(element).find('select[name=popup_on_launch]').val();

        form_data.append('file', file_data);
        form_data.append('display_name', display_name);
        form_data.append('has_score', has_score);
        form_data.append('enable_navigation_menu', enable_navigation_menu);
        form_data.append('enable_fullscreen_button', enable_fullscreen_button);
        form_data.append('weight', weight);
        form_data.append('width', width);
        form_data.append('height', height);
        form_data.append('navigation_menu_width', navigation_menu_width);
        form_data.append('popup_on_launch', popup_on_launch);
        runtime.notify('save', {
            state: 'start',
            message: file_data ? trans('Uploading') : trans('Saving')
        });

        if (file_data) {
            showStatus(trans('Uploading package...'), 0);
        }

        $saveButton.addClass("disabled");
        $.ajax({
            url: handlerUrl,
            dataType: 'json',
            cache: false,
            contentType: false,
            processData: false,
            data: form_data,
            type: "POST",
            // Opt out of Studio's global ajaxError handler, which reports every failed
            // request as "Studio's having trouble saving your work".
            notifyOnError: false,
            xhr: function () {
                var xhr = $.ajaxSettings.xhr();
                if (file_data && xhr.upload) {
                    xhr.upload.addEventListener('progress', function (event) {
                        if (!event.lengthComputable) {
                            return;
                        }
                        var percent = Math.round((event.loaded / event.total) * 100);
                        if (percent < 100) {
                            showStatus(trans('Uploading package...') + ' ' + percent + '%', percent);
                        } else {
                            // Extraction starts now and reports no progress.
                            showStatus(trans('Extracting package on the server, please wait...'), null);
                        }
                    });
                }
                return xhr;
            },
            complete: function () {
                $saveButton.removeClass("disabled");
            },
            success: function (response) {
                var errors = (response && response.errors) || [];
                hideStatus();
                if (errors.length > 0) {
                    dismissSavingIndicator();
                    errors.forEach(function (error) {
                        notifyError(trans('Scorm component save error'), error);
                    });
                } else {
                    runtime.notify('save', {
                        state: 'end'
                    });
                }
            },
            error: function (jqXHR, textStatus) {
                var failure = describeFailure(jqXHR, textStatus);
                dismissSavingIndicator();
                if (failure.stillProcessing) {
                    showStatus(trans('Still extracting on the server. Reload the page in a few minutes.'), null);
                } else {
                    hideStatus();
                }
                notifyError(failure.title, failure.message);
            }
        });

    });

    $(element).find('.cancel-button').bind('click', function () {
        runtime.notify('cancel', {});
    });

}
