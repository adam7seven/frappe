export function get_select_options_value_label(options, options_has_label = false, remove_empty = false) {
    if (!options) {
        return [];
    }
    if (typeof options !== "string") {
        return [];
    }

    let option_list = options.split("\n");
    if (remove_empty) {
        option_list = option_list.filter(x => x);
    }

    let result = []
    if (!options_has_label) {
        result = option_list.map(item => ({ label: __(item), value: item }));
        return result;
    }

    //如果选项中包含逗号，则按逗号隔开
    for (var i = 0; i < option_list.length; i++) {
        var opt = option_list[i];
        var comma_index = opt.indexOf(",")
        if (comma_index === 0) {
            result.push({ label: __(opt.substring(1)), value: "" });
        }
        else if (comma_index > 0) {
            result.push({ label: __(opt.substring(comma_index + 1)), value: opt.substring(0, comma_index) });
        }
    }
    return result;
}