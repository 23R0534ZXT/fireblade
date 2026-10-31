using System;
using System.ComponentModel;
using System.IO;
using System.Web;
public sealed class LegacyReader {
 public BindingList<LegacyRow> DataList {get;}=new BindingList<LegacyRow>();
 public void ProcessFile(string path) {DataList.Add(new LegacyRow {Text=HttpUtility.HtmlEncode(File.ReadAllText(path))});}
}
public sealed class LegacyRow {public string Text{get;set;} }
public sealed class LegacyEncode {
 public string Name {get {return "LegacyEncode";}}
 public object Evaluate(params object[] values) {return HttpUtility.HtmlEncode(values[0].ToString());}
 public Type ResultType(params Type[] values) {return typeof(string);}
}
