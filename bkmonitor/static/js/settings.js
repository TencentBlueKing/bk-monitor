//-----------------------------------------------------------
/**
 * 调试配置，请只在这个地方进行设置，不要动其他代码
 */
var debug = true; // 是否是调试模式，注意：在上传代码的时候，要改为false
//-----------------------------------------------------------

//以下公用代码区域，使用范围非常广，请勿更改--------------------------------
//403 ajax 请求错误时artdialog提示
document.write("<style>.global-el-message-box {width: auto !important;} </style>");
if (window.Vue === undefined) {
	document.write(" <script lanague=\"javascript\" src=\""+static_url+"monitor/old.js\"> <\/script>");
}

//csrftoken处理js
function choose_csrftoken_by_jquery(){
	var jquery_version = $().jquery;
	var current_version = jquery_version.split('.');
	var compare_version = [1, 10, 0];
	var result = true;
	for(var i = 0; i < 3 && result; i++){
		if(parseInt(current_version[i]) < compare_version[i]){
			result = false;
		}else if(parseInt(current_version[i]) > compare_version[i]){
			break;
		}
	}
	//大于或等于1.10.0
	if(result){
		document.write(" <script lanague=\"javascript\" src=\""+static_url+"js/csrftoken_v3.js?v=" + static_version + "\"> <\/script>");
	}
	else{
		document.write(" <script lanague=\"javascript\" src=\""+static_url+"js/csrftoken.js?v=" + static_version + "\"> <\/script>");
	}
}
choose_csrftoken_by_jquery();

/*
 * 打开登录窗口
 */
function open_login_dialog(src){
	var login_html = '<div style="overflow: hidden;width: 490px;"><iframe name="iframe_401" scrolling="no" frameborder="0" src="'+src+'" style="width:490px;height: 460px;"></iframe></div>';
    Vue.prototype.$alert(login_html, '', {
        dangerouslyUseHTMLString: true,
        showCancelButton: false,
        showConfirmButton: false,
		customClass: 'global-el-message-box',
        callback: function() {}
    });
}

/**
 * 关闭登录框
 */
function close_login_dialog(){

    try {
        window.close_login_dialog_after();
    } catch(err){}
}

/*
 *  登录提示
 * 不在蓝鲸平台中，则跳转到蓝鲸平台中
 */
function jump_to_pt(app_code){
	var d_tips = gettext("温馨提示：请在蓝鲸平台中使用该应用！<br>即将跳转至蓝鲸平台！")
	var tips =arguments[1]? arguments[1]:d_tips;
	var bk_url = window.location.host;
	// 当前应用的宣传链接
	if(app_code != ''){
		var jump_url =  'http://'+bk_url + "/?app=" + app_code;
	}else{
		var jump_url =  'http://'+bk_url + "/";
	}
	Vue.prototype.$confirm(gettext('请在蓝鲸平台中使用该应用！点击确定跳转至蓝鲸平台'), gettext('温馨提示'), {
	    confirmButtonText: gettext('确定'),
	    showCancelButton: false,
	    type: 'warning',
		center: true,
	}).then(function () {
		window.top.location = jump_url;
	}).catch(function(){});
}

function get_error_msg(message) {
    // 递归获取错误信息
    var msg_list = [];
    function get_msg(msg) {
        if (typeof(msg) === 'string') {
            msg_list.push(msg);
            return;
        }
        for (var i in msg) {
            if (isNaN(i) && $.inArray(i, ['non_field_errors', 'details', 'detail']) === -1) {
                // 不是数字则记录下来
                msg_list.push(i);
            }
            get_msg(msg[i]);
            break;
        }
    }
    if (typeof(message) === 'string') {
        msg_list.push(message);
    } else {
        get_msg(message);
    }
    var msg = msg_list.pop();
    var name = msg_list.pop();
    if (name) {
        msg = name + ": " + msg;
    }
    return msg;
}

/**
 * ajax全局设置
 */
// 在这里对ajax请求做一些统一公用处理
$.ajaxSetup({
//	timeout: 8000,
	statusCode: {
		400: function(xhr) {
			// alert_topbar(get_error_msg(xhr.responseJSON.message), 'error');
			window.Vue.prototype.$bkMessage({
				isSingleLine: false,
				message: get_error_msg(xhr.responseJSON.message),
				theme: 'error'
			})
		},
	    401: function(xhr) {
				// 正式环境中判断是否在蓝鲸平台中打开
				const handleLoginExpire = () => {
					if (Vue.prototype.$platform.openpaas){
							window.location.reload();
					}else{
							var _src = xhr.responseText;
							// 判断返回的url是否正确
							var is_src  = _src.indexOf('http://');
							if(is_src != 0){
									var tips = gettext("温馨提示：用户信息验证失败！<br>即将跳转至登录页面！")
									jump_to_pt(app_code, tips);
							}else{
									// 判断是否是在蓝鲸平台中打开
									try{
											window.top.BLUEKING.corefunc.open_login_dialog(_src);
									}catch(err){
											open_login_dialog(_src);
									}
							}
					}
				}
				try {
					const data = JSON.parse(xhr.responseText)
					if (data.has_plain) {
						window.top.BLUEKING.corefunc.open_login_dialog(data['login_url'], data['width'], data['height'])
					} else {
						handleLoginExpire()
					}
				}catch (_) {
					handleLoginExpire()
				}
	    },
	    402: function() {
	    	//@APP开发者: 请注意,如果某操作需要使用ajax请求敏感系统,务必要在包含该操作的页面的view函数上
	    	//					 加上@tof_check_session来登录敏感系统.
	    	//					(因为登录敏感需要页面重定向, 而ajax无法进行重定向操作)
			//这里是不应该出现的错误(ajax请求敏感系统前没有登录)
			window.Vue.prototype.$bkMessage({
				isSingleLine: false,
				message: gettext("还没有登录到敏感系统, 请通过刷新当前页面来登录到敏感系统.\n") +
				gettext("如果刷新后依然无法登录, 请通知APP开发者进行改正(敏感系统的ajax请求不符合规范). "),
				theme: 'error'
			})
	    	// alert(gettext("还没有登录到敏感系统, 请通过刷新当前页面来登录到敏感系统.\n") +
			// 		  gettext("如果刷新后依然无法登录, 请通知APP开发者进行改正(敏感系统的ajax请求不符合规范). "));
			return;
	    },
	    // 403: function(xhr) {
	    // 	// 主要用于敏感权限系统的无权限或验证出错的情况
	    // 	var _src = xhr.responseText;
	    // 	try {
	    // 		var jsonObj = JSON.parse(_src)
		// 		var msg = get_error_msg(jsonObj.message)
		// 		_src = msg || _src
		// 	} catch (e) {}
		// 	window.Vue.prototype.$bkMessage({
		// 		message: '403 FORBIDDEN',
		// 		theme: 'error'
		// 	})
	    // 	// Vue.prototype.$alert(_src, '403 FORBIDDEN', {
		// 	// 	dangerouslyUseHTMLString: true,
		// 	// 	showCancelButton: false,
		// 	// 	showConfirmButton: false,
		// 	// 	customClass: 'global-el-message-box',
		// 	// 	callback: function() {}
		// 	// });
	    // },
	    500: function(xhr, textStatus) {
	    	// 异常
	    	if(debug){
				window.Vue.prototype.$bkMessage({
					isSingleLine: false,
					message: gettext("系统出现异常(")+xhr.status+'):' + xhr.responseText,
					theme: 'error'
				})
	    		// alert(gettext("系统出现异常(")+xhr.status+'):' + xhr.responseText);
	    	}
	    	else{
				window.Vue.prototype.$bkMessage({
					message: gettext("系统出现异常, 请记录下错误场景并与开发人员联系, 谢谢!"),
					theme: 'error'
				})
	    		// alert(gettext("系统出现异常, 请记录下错误场景并与开发人员联系, 谢谢!"));
	    	}
	    },
		502: function(xhr, textStatus) {
			window.Vue.prototype.$bkMessage({
				isSingleLine: false,
				message: gettext("系统出现异常(")+xhr.status+'):' + xhr.responseText,
				theme: 'error'
			})
		},
		403: function (xhr, textStatus) {
			const h = Vue.prototype.$bus.$createElement
			window.Vue.prototype.$bkInfo({
				title: '',
				maskClose: false,
				subHeader: h('div', {
					class: {
						'exception-wrap': true
					}
				},[
					h('bk-exception', {
						props: {
							type: '403',
							scene: 'part'
						},
						class: {
							'exception-wrap-item': true,
							'exception-part': true
						}
					},[
						h('span',{}, xhr.responseJSON.message),
						h('div', {
							class: {
								'text-wrap': true,
								'text-part': true
							}
						},[h('a', {
							class: {
								'text-btn': true
							},
							attrs: {
								href: xhr.responseJSON.data.apply_url,
								target: '_blank'
							},
							style: {
								color: '#3A84FF',
								fontSize: '14px'
							}
						}, '去申请')])
					])
				]),
				theme: 'error',
				showFooter: false
			})
		}
	}
});
/**
 * xssCheck 将用js渲染的html进行转义
 * @param str 需要转义的字符串
 * @param reg 需要转义的字符等，可选参数
*/
function xssCheck(str,reg){
    return str ? str.replace(reg || /[&<">'](?:(amp|lt|quot|gt|#39|nbsp|#\d+);)?/g, function (a, b) {
        if(b){
            return a;
        }else{
            return {
                '<':'&lt;',
                '&':'&amp;',
                '"':'&quot;',
                '>':'&gt;',
                "'":'&#39;',
            }[a]
        }
    }) : '';
}
