String.prototype.format = function () {
  var args = arguments;
  return this.replace(/{(\d+)}/g, function (match, number) {
    return typeof args[number] != 'undefined' ? args[number] : match;
  });
};

function getCookie(name) {
  var reg = new RegExp("(^| )" + name + "=([^;]*)(;|$)");
  var arr = document.cookie.match(reg);
  return arr ? unescape(arr[2]) : null;
}

function setCookie(name, value, expires_days = 365) {
  var domain = location.host.split(":")[0];
  if (expires_days) {
    var exp = new Date();
    exp.setTime(exp.getTime() + expires_days * 86400000 + 8 * 3600000)
    document.cookie = name + '=' + value + ';path=/;domain=' + domain + ';expires=' + exp.toUTCString()
  } else {
    document.cookie = name + "=" + value + ";path=/;domain=" + domain + ";"
  }
}

function removeCookie(name) {
  setCookie(name, "", -1);
}

function parseUrl(url) {
  if (typeof url == 'undefined') {
    url = location.href;
  }
  var segment = url.match(/^(\w+\:\/\/)?([\w\d]+(?:\.[\w]+)*)?(?:\:(\d+))?(\/[^?#]*)?(?:\?([^#]*))?(?:#(.*))?$/);
  if (!segment[3]) {
    segment[3] = '80';
  }
  var param = {};
  if (segment[5]) {
    var pse = segment[5].match(/([^=&]+)=([^&]+)/g);
    if (pse) {
      for (var i = 0; i < pse.length; i++) {
        param[pse[i].split('=')[0]] = pse[i].split('=')[1];
      }
    }
  }
  return {
    url: segment[0],
    sechme: segment[1],
    host: segment[2],
    port: segment[3],
    path: segment[4],
    queryString: segment[5],
    fregment: segment[6],
    param: param
  };
};


layui.config({ base: '/static/src/js/' }).use(['layer', 'element', 'laytpl', 'form', 'md5'], function () {
  var layer = layui.layer
  var element = layui.element
  var laytpl = layui.laytpl
  var form = layui.form
  var md5 = layui.md5
  var $ = layui.$

  function changeUserState(user) {
    $('.logout').removeClass('hidden')
    $('.login').addClass('hidden')
    $('.username').text(user.username)
  }

  function checkUser() {
    $.get('/user', function (ret) {
      if (!ret.err) {
        localStorage.setItem('user', JSON.stringify(ret))
        changeUserState(ret)
      } else {
        $('.login').removeClass('hidden')
      }
    })
  }

  checkUser()

  var clipboard = new ClipboardJS('.btn-copy', {
    target: function (trigger) {
      return $(trigger).parents('tr').find('input')[0]
    }
  })
  clipboard.on('success', function (e) {
    layer.msg('已复制到剪贴板', { time: 2000 })
    e.clearSelection()
  })

  clipboard.on('error', function (e) {
    layer.msg('复制出错，请手动复制', { time: 2000 })
  })

  $('.signup input[name=email], .signup input[name=username]').on('change', function () {
    var key = $(this).attr('name')
    var value = $(this).val()
    $.get('/check?{0}={1}'.format(key, value), function (ret) {
      if (ret.err) {
        layer.msg(ret.msg)
      }
    })
  })

  $('input[name=password]').on('change', function () {
    var passwords = $(this).parents('form').find('input[name=password]')
    if (passwords.length == 2 &&
      $(passwords[0]).val() && $(passwords[1]).val() &&
      $(passwords[0]).val() != $(passwords[1]).val()) {
      layer.msg('两次输入的密码不一致')
      $(passwords[0]).val('')
      $(passwords[1]).val('')
    }
  })

  $('.btn-send').on('click', function () {
    var email = $(this).parents('form').find('input[name=email]').val()
    if (email) {
      $(this).addClass('layui-btn-disabled')
      var _this = this
      var action = location.pathname.slice(1)
      var data = { email: email }
      $.get('/email/' + action, data, function (ret) {
        if (ret.err) layer.msg(ret.msg)
        else layer.msg('验证码已发送到您的邮箱')
        $(_this).removeClass('layui-btn-disabled')
      })
    } else {
      layer.msg('请输入用户名或邮箱')
    }
  })

  $('.btn-manage').on('click', function() {
    var id = $(this).data('id')
    var action = $(this).data('action')
    $.post(location.path, {'id': id, 'action': action}, function(ret){
      if(ret.err) layer.msg(ret.msg)
      else {
        layer.msg('设置成功')
        location.reload()
      }
    })
  })

  $('.btn-kindle').on('click', function() {
    var tr = $(this).parents("tr");
    var url = tr.find("a").attr("href");
    layer.msg('正在推送中，请稍后', {time: 50000})
    $.ajax({
      method: 'PUT',
      url: url,
      data: {'action': 'kindle'},
      success: function(ret){
        if(ret.err) layer.msg(ret.msg)
        else {
          layer.msg('推送成功')
        }
      },
      error: function(){
        layer.msg('推送失败')
      }
    })
  })


  $('.btn-share').on('click', function() {
    var tr = $(this).parents("tr");
    var url = tr.find("a").attr("href");
    layer.prompt({
      formType: 2,
      value: '1',
      title: '请输入分享天数',
      area: ['200px', '50px'] //自定义文本域宽高
    }, function(value, index, elem){
      $.ajax({
        method: 'PUT',
        url: url,
        data: {'days': value},
        success: function(ret){
          if(ret.err) layer.msg(ret.msg)
          else {
           // $("body").append('<button class="btn-copy" id="copy-share-url" data-clipboard-text="https://' + location.hostname + '/share/' + ret.id + '">Copy</button>');
           // $("#copy-share-url").attr('data-clipboard-text', 'https://' + location.hostname + '/share/' + ret.id);
           // $("#copy-share-url").trigger('click');
            layer.msg('分享成功，跳转到分享管理页')
            setTimeout(function(){ 
              location.href = '/manage/share';
            }, 1000)
          }
        },
        error: function(){
          layer.msg('分享失败')
        }
      })
      layer.close(index);
    });
  })

  $('.btn-cancel-share').on('click', function(){
    var id = $(this).data('id');
    layer.confirm('确定取消？', {icon: 3, title:'提示'}, function(){
      $.post(location.path, {'id': id}, function(ret){
        if(ret.err) layer.msg(ret.msg)
        else {
           layer.msg('取消成功')
          location.reload()
        }
      })
    })
  })

  form.on('submit(default)', function (data) {
    $.ajax({
      type: data.form.getAttribute('method'),
      url: data.form.getAttribute('action'),
      data: data.field,
      success: function (ret) {
        if (ret.err) layer.msg(ret.msg)
        else if (data.form.getAttribute('href')) location.href = data.form.getAttribute('href')
        else layer.msg('提交成功')
      },
      error: function () {
        layer.msg('提交失败')
      }
    })
    return false
  })

})
