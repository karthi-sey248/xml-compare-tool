(function(){
  const USER_ID='admin';
  const PASSWORD='admin123';
  const SESSION_KEY='xmlCompareAuth';
  window.XMLCompareAuth={
    login:function(u,p){if(u===USER_ID&&p===PASSWORD){sessionStorage.setItem(SESSION_KEY,'1');return true;}return false;},
    logout:function(){sessionStorage.removeItem(SESSION_KEY);window.location.href='login.html';},
    isLoggedIn:function(){return sessionStorage.getItem(SESSION_KEY)==='1';},
    guard:function(){if(!this.isLoggedIn()){window.location.href='login.html';}}
  };
})();
